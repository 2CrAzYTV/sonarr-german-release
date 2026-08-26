import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import unquote, quote

import httpx
from bs4 import BeautifulSoup


@dataclass
class ProviderStatus:
    name: str
    configured: bool
    active: bool
    note: str


class WikimediaProvider:
    """Keyless Wikidata + German Wikipedia provider.

    Wikidata is used only for exact identifier matching via IMDb/TheTVDB IDs.
    German Wikipedia is parsed through the official MediaWiki Action API.
    Only tables that explicitly identify a German/German-language first-air
    date are accepted as Germany-specific release observations.
    """

    name = "wikipedia_de"
    wikidata_sparql_url = "https://query.wikidata.org/sparql"
    dewiki_api_url = "https://de.wikipedia.org/w/api.php"
    user_agent = (
        "SonarrGermanRelease/0.3.1 "
        "(https://github.com/2CrAzYTV/sonarr-german-release)"
    )

    month_names = {
        "januar": 1,
        "februar": 2,
        "märz": 3,
        "maerz": 3,
        "april": 4,
        "mai": 5,
        "juni": 6,
        "juli": 7,
        "august": 8,
        "september": 9,
        "oktober": 10,
        "november": 11,
        "dezember": 12,
    }

    def __init__(self):
        self._mapping_cache: dict[tuple[str | None, int | None], dict | None] = {}
        self._page_cache: dict[str, str] = {}
        self._dates_cache: dict[str, dict] = {}

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            configured=True,
            active=True,
            note="Kostenlose Wikimedia APIs · kein API-Key erforderlich",
        )

    async def _get_json(self, url: str, params: dict) -> dict:
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()

    async def wikidata_match(
        self,
        imdb_id: str | None = None,
        tvdb_id: int | None = None,
    ) -> dict | None:
        """Resolve one Wikidata item from exact external identifiers."""
        key = (imdb_id, tvdb_id)
        if key in self._mapping_cache:
            return self._mapping_cache[key]

        clauses = []
        if imdb_id:
            safe_imdb = imdb_id.replace('"', "")
            clauses.append(f'{{ ?item wdt:P345 "{safe_imdb}" . }}')
        if tvdb_id:
            clauses.append(f'{{ ?item wdt:P4835 "{int(tvdb_id)}" . }}')

        if not clauses:
            self._mapping_cache[key] = None
            return None

        query = f'''
SELECT DISTINCT ?item ?article WHERE {{
  {' UNION '.join(clauses)}
  OPTIONAL {{
    ?article schema:about ?item ;
             schema:isPartOf <https://de.wikipedia.org/> .
  }}
}}
LIMIT 5
'''
        data = await self._get_json(
            self.wikidata_sparql_url,
            {"query": query, "format": "json"},
        )
        rows = ((data.get("results") or {}).get("bindings") or [])
        if not rows:
            self._mapping_cache[key] = None
            return None

        # Prefer a match that has a German Wikipedia sitelink.
        rows.sort(key=lambda row: 0 if row.get("article") else 1)
        row = rows[0]
        item_url = ((row.get("item") or {}).get("value") or "")
        article_url = ((row.get("article") or {}).get("value") or "")
        qid = item_url.rsplit("/", 1)[-1] if item_url else None
        dewiki_title = None
        if article_url:
            dewiki_title = unquote(article_url.rsplit("/wiki/", 1)[-1]).replace("_", " ")

        result = {
            "qid": qid,
            "dewiki_title": dewiki_title,
            "dewiki_url": article_url or None,
        }
        self._mapping_cache[key] = result
        return result

    async def _parse_page(self, title: str, prop: str = "text|links") -> dict:
        return await self._get_json(
            self.dewiki_api_url,
            {
                "action": "parse",
                "page": title,
                "prop": prop,
                "format": "json",
                "formatversion": 2,
                "redirects": 1,
            },
        )

    async def page_candidates(self, title: str) -> list[str]:
        """Return the article plus likely episode/season subpages."""
        try:
            data = await self._parse_page(title, prop="links")
        except Exception:
            return [title]

        candidates = [title]
        links = ((data.get("parse") or {}).get("links") or [])
        base = title.split("(", 1)[0].strip().lower()

        for item in links:
            link_title = item.get("title") or ""
            low = link_title.lower()
            likely_episode_page = (
                "episodenliste" in low
                or "liste der episoden" in low
                or bool(re.search(r"\bstaffel\s*\d+\b", low))
            )
            related = base and (base[:18] in low or low.startswith(base[:12]))
            if likely_episode_page and related and link_title not in candidates:
                candidates.append(link_title)
            if len(candidates) >= 8:
                break

        return candidates

    async def page_html(self, title: str) -> str:
        if title in self._page_cache:
            return self._page_cache[title]
        data = await self._parse_page(title, prop="text")
        html = ((data.get("parse") or {}).get("text") or "")
        self._page_cache[title] = html
        return html

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()

    @staticmethod
    def _expanded_cells(row) -> list[str]:
        result = []
        for cell in row.find_all(["th", "td"], recursive=False):
            text = WikimediaProvider._clean_text(cell.get_text(" ", strip=True))
            try:
                colspan = max(1, int(cell.get("colspan", 1)))
            except (TypeError, ValueError):
                colspan = 1
            result.extend([text] * colspan)
        return result

    def _date_to_iso(self, text: str) -> str | None:
        clean = self._clean_text(text)
        numeric = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", clean)
        if numeric:
            day, month, year = map(int, numeric.groups())
            try:
                return datetime(year, month, day).strftime("%Y-%m-%dT00:00:00")
            except ValueError:
                return None

        named = re.search(
            r"\b(\d{1,2})\.\s*(Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{4})\b",
            clean,
            flags=re.IGNORECASE,
        )
        if named:
            day = int(named.group(1))
            month = self.month_names.get(named.group(2).lower())
            year = int(named.group(3))
            if month:
                try:
                    return datetime(year, month, day).strftime("%Y-%m-%dT00:00:00")
                except ValueError:
                    return None
        return None

    @staticmethod
    def _season_from_context(table, page_title: str) -> int | None:
        contexts = [page_title]
        caption = table.find("caption")
        if caption:
            contexts.append(caption.get_text(" ", strip=True))
        heading = table.find_previous(["h2", "h3", "h4", "h5"])
        if heading:
            contexts.append(heading.get_text(" ", strip=True))

        for context in contexts:
            match = re.search(r"\bStaffel\s*(\d+)\b", context, flags=re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def _header_score(text: str, kind: str) -> int:
        low = text.lower()
        if kind == "de_date":
            if "deutsche erstausstrahlung" in low or "deutschsprachige erstausstrahlung" in low:
                return 100
            if "erstausstrahlung" in low and ("deutsch" in low or "deutschland" in low):
                return 90
            if "deutschland" in low and ("ausstrahlung" in low or "premiere" in low):
                return 80
        if kind == "episode":
            if "nr. (st.)" in low or "nr. (staffel" in low or "nr. in staffel" in low:
                return 100
            if "folge" in low and "gesamt" not in low:
                return 80
            if "episode" in low and "gesamt" not in low:
                return 70
        return 0

    def extract_german_dates(self, page_title: str, html: str) -> dict[tuple[int, int], dict]:
        """Extract only explicitly Germany-labelled first-air dates."""
        soup = BeautifulSoup(html, "html.parser")
        result: dict[tuple[int, int], dict] = {}
        page_url = f"https://de.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'))}"

        for table in soup.find_all("table"):
            rows = table.find_all("tr", recursive=False)
            if not rows:
                rows = table.find_all("tr")
            if len(rows) < 2:
                continue

            header_rows = []
            data_start = 0
            for index, row in enumerate(rows[:5]):
                cells = row.find_all(["th", "td"], recursive=False)
                if not cells:
                    cells = row.find_all(["th", "td"])
                has_td = any(cell.name == "td" for cell in cells)
                if has_td:
                    data_start = index
                    break
                header_rows.append(self._expanded_cells(row))
                data_start = index + 1

            width = max((len(row) for row in header_rows), default=0)
            if width == 0:
                continue
            combined_headers = []
            for col in range(width):
                parts = []
                for header in header_rows:
                    if col < len(header) and header[col] and header[col] not in parts:
                        parts.append(header[col])
                combined_headers.append(" ".join(parts))

            de_scores = [self._header_score(text, "de_date") for text in combined_headers]
            if not de_scores or max(de_scores) == 0:
                continue
            de_col = de_scores.index(max(de_scores))

            ep_scores = [self._header_score(text, "episode") for text in combined_headers]
            ep_col = ep_scores.index(max(ep_scores)) if ep_scores and max(ep_scores) else None

            # If there are two generic Nr. columns, the second usually means
            # the number within the season. Use it only when no stronger label exists.
            if ep_col is None:
                nr_cols = [
                    index for index, text in enumerate(combined_headers)
                    if re.search(r"\bnr\.?\b", text.lower())
                ]
                if nr_cols:
                    ep_col = nr_cols[1] if len(nr_cols) > 1 else nr_cols[0]

            season = self._season_from_context(table, page_title)

            for row in rows[data_start:]:
                cells = self._expanded_cells(row)
                if de_col >= len(cells):
                    continue
                release_date = self._date_to_iso(cells[de_col])
                if not release_date:
                    continue

                row_text = self._clean_text(row.get_text(" ", strip=True))
                row_season = season
                episode_number = None

                se_match = re.search(r"\bS(\d{1,2})E(\d{1,3})\b", row_text, flags=re.IGNORECASE)
                if se_match:
                    row_season = int(se_match.group(1))
                    episode_number = int(se_match.group(2))

                if episode_number is None and ep_col is not None and ep_col < len(cells):
                    ep_match = re.search(r"\b(\d{1,3})\b", cells[ep_col])
                    if ep_match:
                        episode_number = int(ep_match.group(1))

                if row_season is None or episode_number is None:
                    continue

                result[(row_season, episode_number)] = {
                    "release_date": release_date,
                    "confidence": "high",
                    "note": f"Deutsche Erstausstrahlung laut Wikipedia DE · {page_url}",
                    "source_url": page_url,
                    "page_title": page_title,
                }

        return result

    async def german_episode_dates(
        self,
        imdb_id: str | None = None,
        tvdb_id: int | None = None,
    ) -> dict:
        mapping = await self.wikidata_match(imdb_id=imdb_id, tvdb_id=tvdb_id)
        if not mapping or not mapping.get("dewiki_title"):
            return {"mapping": mapping, "dates": {}, "pages_checked": 0}

        title = mapping["dewiki_title"]
        if title in self._dates_cache:
            cached = self._dates_cache[title]
            return {"mapping": mapping, **cached}

        dates: dict[tuple[int, int], dict] = {}
        candidates = await self.page_candidates(title)
        checked = 0
        for candidate in candidates:
            try:
                html = await self.page_html(candidate)
            except Exception:
                continue
            checked += 1
            extracted = self.extract_german_dates(candidate, html)
            for key, observation in extracted.items():
                dates.setdefault(key, observation)

        payload = {"dates": dates, "pages_checked": checked}
        self._dates_cache[title] = payload
        return {"mapping": mapping, **payload}
