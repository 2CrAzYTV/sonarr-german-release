import re
import time
import unicodedata
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


@dataclass
class ProviderStatus:
    name: str
    configured: bool
    active: bool
    note: str


class FernsehserienProvider:
    """German episode-premiere provider based on public fernsehserien.de guides.

    The series overview is used only to discover the canonical season-guide
    links. Detailed season pages are then parsed for explicit German TV or
    streaming premiere labels. Responses are cached for six hours.
    """

    name = "fernsehserien_de"
    base_url = "https://www.fernsehserien.de"
    cache_ttl_seconds = 6 * 60 * 60
    user_agent = (
        "SonarrGermanRelease/0.3.10 "
        "(+https://github.com/2CrAzYTV/sonarr-german-release; low-frequency metadata lookup)"
    )

    def __init__(self):
        self._page_cache: dict[str, tuple[float, str | None]] = {}

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            configured=True,
            active=True,
            note="Kostenlose öffentliche Episodenguides · Staffel-Detailseiten · explizite deutsche TV-/Streaming-Premieren · 6h Cache",
        )

    @staticmethod
    def _clean_title(value: str | None) -> str:
        if not value:
            return ""
        value = re.sub(r"\s*\((?:DE|Germany|Deutschland)\)\s*$", "", value, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _slug(value: str) -> str:
        value = FernsehserienProvider._clean_title(value)
        value = value.replace("&", " and ")
        value = value.replace("’", "'")
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        value = value.casefold().replace("ß", "ss")
        value = re.sub(r"['’]", "", value)
        value = re.sub(r"[^a-z0-9]+", "-", value)
        return value.strip("-")

    @staticmethod
    def _normal_title(value: str | None) -> str:
        if not value:
            return ""
        value = FernsehserienProvider._clean_title(value)
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        value = value.casefold().replace("&", " and ").replace("ß", "ss")
        value = re.sub(r"[^a-z0-9]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    @classmethod
    def _title_matches(cls, expected_titles: list[str], actual_title: str) -> bool:
        actual = cls._normal_title(actual_title)
        if not actual:
            return False
        actual_words = set(actual.split())

        for expected_title in expected_titles:
            expected = cls._normal_title(expected_title)
            if not expected:
                continue
            if expected == actual or expected in actual or actual in expected:
                return True
            expected_words = set(expected.split())
            if expected_words:
                overlap = len(expected_words & actual_words) / len(expected_words)
                if overlap >= 0.8:
                    return True
        return False

    async def _page(self, url: str) -> str | None:
        cached = self._page_cache.get(url)
        now = time.monotonic()
        if cached and now - cached[0] < self.cache_ttl_seconds:
            return cached[1]

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
        }
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
            if response.status_code == 404:
                self._page_cache[url] = (now, None)
                return None
            response.raise_for_status()
            html = response.text
            self._page_cache[url] = (now, html)
            return html
        except Exception:
            self._page_cache[url] = (now, None)
            return None

    @staticmethod
    def _date_iso(value: str) -> str | None:
        match = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", value)
        if not match:
            return None
        day, month, year = (int(part) for part in match.groups())
        if not (1 <= day <= 31 and 1 <= month <= 12):
            return None
        return f"{year:04d}-{month:02d}-{day:02d}T00:00:00"

    @classmethod
    def _parse_dates(cls, html: str, source_url: str) -> dict[tuple[int, int], dict]:
        soup = BeautifulSoup(html, "html.parser")
        text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

        starts = list(re.finditer(r"\bStaffel\s+(\d+)\s*,\s*Folge\s+(\d+)\b", text, flags=re.IGNORECASE))
        dates: dict[tuple[int, int], dict] = {}
        premiere_pattern = re.compile(
            r"\bDeutsche\s+(Streaming-Premiere|TV-Premiere|Free-TV-Premiere|Premiere)\s+"
            r"(?:[A-Za-zÄÖÜäöü]{2,3}\.?\s+)?(\d{1,2}\.\d{1,2}\.\d{4})\b",
            flags=re.IGNORECASE,
        )

        for index, start in enumerate(starts):
            season = int(start.group(1))
            episode = int(start.group(2))
            end = starts[index + 1].start() if index + 1 < len(starts) else min(len(text), start.end() + 2500)
            block = text[start.end():end]
            premiere = premiere_pattern.search(block)
            if not premiere:
                continue
            release_date = cls._date_iso(premiere.group(2))
            if not release_date:
                continue

            premiere_type = premiere.group(1)
            dates[(season, episode)] = {
                "release_date": release_date,
                "confidence": "high",
                "match_method": "season_episode",
                "note": f"Deutsche {premiere_type} laut fernsehserien.de · {source_url}",
                "source_url": source_url,
            }
        return dates

    @staticmethod
    def _candidate_titles(series: dict) -> list[str]:
        candidates: list[str] = []
        title = series.get("title")
        if title:
            candidates.append(title)
        for item in series.get("alternateTitles") or []:
            alt = item.get("title") if isinstance(item, dict) else None
            if alt and alt not in candidates:
                candidates.append(alt)
        return candidates[:8]

    @staticmethod
    def _season_links(html: str, overview_url: str) -> dict[int, str]:
        soup = BeautifulSoup(html, "html.parser")
        links: dict[int, str] = {}
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href") or ""
            match = re.search(r"/episodenguide/staffel-(\d+)/(\d+)(?:[/?#]|$)", href, flags=re.IGNORECASE)
            if not match:
                continue
            season = int(match.group(1))
            links.setdefault(season, urljoin(overview_url, href))
        return links

    async def german_episode_dates(self, series: dict, seasons: set[int] | None = None) -> dict:
        titles = self._candidate_titles(series)
        slugs: list[str] = []
        for title in titles:
            slug = self._slug(title)
            if slug and slug not in slugs:
                slugs.append(slug)

        target_seasons = {int(value) for value in (seasons or set()) if value is not None}

        # Keep network usage predictable: at most four direct series candidates.
        for slug in slugs[:4]:
            overview_url = f"{self.base_url}/{slug}/episodenguide"
            overview_html = await self._page(overview_url)
            if not overview_html:
                continue

            soup = BeautifulSoup(overview_html, "html.parser")
            heading = soup.find("h1")
            actual_title = heading.get_text(" ", strip=True) if heading else ""
            if not self._title_matches(titles, actual_title):
                continue

            season_links = self._season_links(overview_html, overview_url)
            selected = [
                (season, url)
                for season, url in sorted(season_links.items())
                if not target_seasons or season in target_seasons
            ][:4]

            dates: dict[tuple[int, int], dict] = {}
            pages_checked = 1
            season_pages = 0
            for season, season_url in selected:
                season_html = await self._page(season_url)
                if not season_html:
                    continue
                pages_checked += 1
                season_pages += 1
                for key, observation in self._parse_dates(season_html, season_url).items():
                    if key[0] == season:
                        dates[key] = observation

            return {
                "mapped": True,
                "series_title": actual_title,
                "source_url": overview_url,
                "dates": dates,
                "pages_checked": pages_checked,
                "season_pages": season_pages,
                "available_seasons": sorted(season_links),
            }

        return {
            "mapped": False,
            "series_title": None,
            "source_url": None,
            "dates": {},
            "pages_checked": 0,
            "season_pages": 0,
            "available_seasons": [],
        }
