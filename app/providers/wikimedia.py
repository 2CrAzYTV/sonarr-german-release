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
        "SonarrGermanRelease/0.3.2 "
        "(https://github.com/2CrAzYTV/sonarr-german-release)"
    )

    month_names = {
        "januar": 1,
        "jan": 1,
        "februar": 2,
        "feb": 2,
        "märz": 3,
        "maerz": 3,
        "mär": 3,
        "mrz": 3,
        "april": 4,
        "apr": 4,
        "mai": 5,
        "juni": 6,
        "jun": 6,
        "juli": 7,
        "jul": 7,
        "august": 8,
        "aug": 8,
        "september": 9,
        "sep": 9,
        "sept": 9,
        "oktober": 10,
        "okt": 10,
        "november": 11,
        "nov": 11,
        "dezember": 12,
        "dez": 12,
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
            note="Kostenlose Wikimedia APIs · erweiterter DE-Episodenparser · kein API-Key",
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

    async def _search_pages(self, title: str) -> list[str]:
        """Use MediaWiki search to find likely episode-list pages."""
        base = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
        queries = [
            f'intitle:Episodenliste "{base}"',
            f'intitle:Staffel "{base}"',
            f'"{base}" Episodenliste',
        ]
        results: list[str] = []
        for query in queries:
            try:
                data = await self._get_json(
                    self.dewiki_api_url,
                    {
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "srnamespace": 0,
                        "srlimit": 5,
                        "format": "json",
                        "formatversion": 2,
                    },
                )
            except Exception:
                continue
            for item in ((data.get("query") or {}).get("search") or []):
                page_title = item.get("title")
                if page_title and page_title not in results:
                    results.append(page_title)
        return results

    async def page_candidates(self, title: str) -> list[str]:
        """Return article plus linked/searched episode and season pages."""
        candidates = [title]
        try:
            data = await self._parse_page(title, prop="links")
            links = ((data.get("parse") or {}).get("links") or [])
        except Exception:
            links = []

        base = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip().lower()
        base_words = [word for word in re.split(r"\W+", base) if len(word) >= 4]

        for item in links:
            link_title = item.get("title") or ""
            low = link_title.lower()
            likely_episode_page = (
                "episodenliste" in low
                or "liste der episoden" in low
                or "liste von episoden" in low
                or bool(re.search(r"\bstaffel\s*\d+\b", low))
            )
            related = not base_words or any(word in low for word in base_words[:3])
            if likely_episode_page and related and link_title not in candidates:
                candidates.append(link_title)

        for page_title in await self._search_pages(title):
            low = page_title.lower()
            related = not base_words or any(word in low for word in base_words[:3])
            if related and page_title not in candidates:
                candidates.append(page_title)

        return candidates[:12]

    async def page_html(self, title: str) -> str:
        if title in self._page_cache:
            return self._page_cache[title]
        data = await self._parse_page(title, prop="text")
        html = ((data.get("parse") or {}).get("text") or "")
        self._page_cache[title] = html
        return html

    @staticmethod
    def _clean_text(value: str) -> str:
        value = value.replace("\xa0", " ").replace("\u202f", " ")
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _cell_text(cell) -> str:
        return WikimediaProvider._clean_text(cell.get_text(" ", strip=True))

    def _table_grid(self, table) -> tuple[list[list[str]], list[bool]]:
        """Expand rowspan/colspan into a rectangular text grid.

        Wikipedia episode tables often use rowspan/colspan in both header and
        data rows. Expanding them first keeps column positions stable.
        """
        grid: list[list[str]] = []
        header_flags: list[bool] = []
        pending: dict[int, tuple[int, str]] = {}

        rows = table.find_all("tr")
        for row in rows:
            direct_cells = row.find_all(["th", "td"], recursive=False)
            if not direct_cells:
                direct_cells = row.find_all(["th", "td"])
            if not direct_cells and not pending:
                continue

            values: list[str] = []
            col = 0
            cells = iter(direct_cells)
            current = next(cells, None)

            while current is not None or pending:
                if col in pending:
                    remaining, text = pending[col]
                    values.append(text)
                    if remaining <= 1:
                        del pending[col]
                    else:
                        pending[col] = (remaining - 1, text)
                    col += 1
                    continue

                if current is None:
                    next_pending = [key for key in pending if key > col]
                    if not next_pending:
                        break
                    while col < min(next_pending):
                        values.append("")
                        col += 1
                    continue

                text = self._cell_text(current)
                try:
                    colspan = max(1, int(current.get("colspan", 1)))
                except (TypeError, ValueError):
                    colspan = 1
                try:
                    rowspan = max(1, int(current.get("rowspan", 1)))
                except (TypeError, ValueError):
                    rowspan = 1

                for offset in range(colspan):
                    values.append(text)
                    if rowspan > 1:
                        pending[col + offset] = (rowspan - 1, text)
                col += colspan
                current = next(cells, None)

            grid.append(values)
            header_flags.append(any(cell.name == "th" for cell in direct_cells))

        width = max((len(row) for row in grid), default=0)
        for row in grid:
            row.extend([""] * (width - len(row)))
        return grid, header_flags

    def _date_to_iso(self, text: str) -> str | None:
        clean = self._clean_text(text)
        clean = re.sub(r"\[[^\]]+\]", "", clean)

        numeric = re.search(r"\b(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})\b", clean)
        if numeric:
            day, month, year = map(int, numeric.groups())
            try:
                return datetime(year, month, day).strftime("%Y-%m-%dT00:00:00")
            except ValueError:
                return None

        named = re.search(
            r"\b(\d{1,2})\.\s*"
            r"(Januar|Jan\.?|Februar|Feb\.?|März|Maerz|Mär\.?|Mrz\.?|April|Apr\.?|Mai|"
            r"Juni|Jun\.?|Juli|Jul\.?|August|Aug\.?|September|Sept?\.?|Oktober|Okt\.?|"
            r"November|Nov\.?|Dezember|Dez\.?)\s+(\d{4})\b",
            clean,
            flags=re.IGNORECASE,
        )
        if named:
            day = int(named.group(1))
            month_name = named.group(2).lower().replace(".", "")
            month = self.month_names.get(month_name)
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

        patterns = [
            r"\bStaffel\s*(\d+)\b",
            r"\b(\d+)\.\s*Staffel\b",
            r"\bSeason\s*(\d+)\b",
        ]
        for context in contexts:
            for pattern in patterns:
                match = re.search(pattern, context, flags=re.IGNORECASE)
                if match:
                    return int(match.group(1))
        return None

    @staticmethod
    def _normal_header(text: str) -> str:
        low = text.lower()
        low = low.replace("–", "-").replace("—", "-")
        low = re.sub(r"[\[\]{}()]", " ", low)
        low = re.sub(r"\s+", " ", low)
        return low.strip()

    @classmethod
    def _header_score(cls, text: str, kind: str) -> int:
        low = cls._normal_header(text)

        if kind == "de_date":
            exact = (
                "deutsche erstausstrahlung",
                "deutschsprachige erstausstrahlung",
                "deutsche premiere",
                "deutschsprachige premiere",
                "de premiere",
                "premiere de",
            )
            if any(value in low for value in exact):
                return 100
            if "erstausstrahlung" in low and any(
                value in low for value in ("deutsch", "deutschland", "de ", " d ")
            ):
                return 95
            if any(value in low for value in ("deutschland", "deutschsprachig")) and any(
                value in low for value in ("ausstrahlung", "premiere", "start")
            ):
                return 90
            if re.search(r"\b(?:dt|de|d)\.?\s*(?:erstausstrahlung|premiere)\b", low):
                return 88

        if kind == "episode":
            if any(value in low for value in (
                "nr. st.", "nr st.", "nr. staffel", "nr staffel",
                "nr. in staffel", "nr in staffel", "episode in staffel",
                "folge in staffel",
            )):
                return 100
            if "staffelfolge" in low:
                return 95
            if "folge" in low and "gesamt" not in low:
                return 80
            if "episode" in low and "gesamt" not in low:
                return 75

        if kind == "season":
            if low in ("staffel", "staffel nr.", "staffelnr.", "staffelnummer", "season"):
                return 100
            if "staffel" in low and "nr" in low:
                return 90

        return 0

    @staticmethod
    def _first_int(text: str) -> int | None:
        match = re.search(r"\b(\d{1,3})\b", text)
        return int(match.group(1)) if match else None

    def extract_german_dates(self, page_title: str, html: str) -> tuple[dict[tuple[int, int], dict], dict]:
        """Extract only explicitly Germany-labelled first-air dates."""
        soup = BeautifulSoup(html, "html.parser")
        result: dict[tuple[int, int], dict] = {}
        page_url = f"https://de.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'))}"
        stats = {
            "tables_seen": 0,
            "de_tables": 0,
            "dated_rows": 0,
            "matched_rows": 0,
        }

        for table in soup.find_all("table"):
            stats["tables_seen"] += 1
            grid, header_flags = self._table_grid(table)
            if len(grid) < 2:
                continue

            header_indices: list[int] = []
            for index, is_header in enumerate(header_flags[:6]):
                if is_header:
                    header_indices.append(index)
                elif header_indices:
                    break
            if not header_indices:
                continue

            width = max(len(grid[index]) for index in header_indices)
            combined_headers = []
            for col in range(width):
                parts = []
                for row_index in header_indices:
                    value = grid[row_index][col] if col < len(grid[row_index]) else ""
                    if value and value not in parts:
                        parts.append(value)
                combined_headers.append(" ".join(parts))

            de_scores = [self._header_score(text, "de_date") for text in combined_headers]
            if not de_scores or max(de_scores) == 0:
                continue
            de_col = de_scores.index(max(de_scores))
            stats["de_tables"] += 1

            ep_scores = [self._header_score(text, "episode") for text in combined_headers]
            ep_col = ep_scores.index(max(ep_scores)) if ep_scores and max(ep_scores) else None

            season_scores = [self._header_score(text, "season") for text in combined_headers]
            season_col = season_scores.index(max(season_scores)) if season_scores and max(season_scores) else None

            if ep_col is None:
                nr_cols = [
                    index for index, text in enumerate(combined_headers)
                    if re.search(r"\bnr\.?\b", self._normal_header(text))
                ]
                if nr_cols:
                    ep_col = nr_cols[1] if len(nr_cols) > 1 else nr_cols[0]

            context_season = self._season_from_context(table, page_title)
            data_start = max(header_indices) + 1

            for values in grid[data_start:]:
                if de_col >= len(values):
                    continue
                release_date = self._date_to_iso(values[de_col])
                if not release_date:
                    continue
                stats["dated_rows"] += 1

                row_text = self._clean_text(" ".join(values))
                row_season = context_season
                episode_number = None

                se_match = re.search(r"\bS(\d{1,2})\s*E(\d{1,3})\b", row_text, flags=re.IGNORECASE)
                if se_match:
                    row_season = int(se_match.group(1))
                    episode_number = int(se_match.group(2))

                if row_season is None and season_col is not None and season_col < len(values):
                    row_season = self._first_int(values[season_col])

                if episode_number is None and ep_col is not None and ep_col < len(values):
                    episode_number = self._first_int(values[ep_col])

                if row_season is None or episode_number is None:
                    continue

                result[(row_season, episode_number)] = {
                    "release_date": release_date,
                    "confidence": "high",
                    "note": f"Deutsche Erstausstrahlung laut Wikipedia DE · {page_url}",
                    "source_url": page_url,
                    "page_title": page_title,
                }
                stats["matched_rows"] += 1

        return result, stats

    async def german_episode_dates(
        self,
        imdb_id: str | None = None,
        tvdb_id: int | None = None,
    ) -> dict:
        mapping = await self.wikidata_match(imdb_id=imdb_id, tvdb_id=tvdb_id)
        if not mapping or not mapping.get("dewiki_title"):
            return {
                "mapping": mapping,
                "dates": {},
                "pages_checked": 0,
                "tables_seen": 0,
                "de_tables": 0,
                "dated_rows": 0,
                "matched_rows": 0,
            }

        title = mapping["dewiki_title"]
        if title in self._dates_cache:
            cached = self._dates_cache[title]
            return {"mapping": mapping, **cached}

        dates: dict[tuple[int, int], dict] = {}
        candidates = await self.page_candidates(title)
        totals = {
            "pages_checked": 0,
            "tables_seen": 0,
            "de_tables": 0,
            "dated_rows": 0,
            "matched_rows": 0,
        }

        for candidate in candidates:
            try:
                html = await self.page_html(candidate)
            except Exception:
                continue
            totals["pages_checked"] += 1
            extracted, stats = self.extract_german_dates(candidate, html)
            for key in ("tables_seen", "de_tables", "dated_rows", "matched_rows"):
                totals[key] += stats.get(key, 0)
            for key, observation in extracted.items():
                dates.setdefault(key, observation)

        payload = {"dates": dates, **totals}
        self._dates_cache[title] = payload
        return {"mapping": mapping, **payload}
