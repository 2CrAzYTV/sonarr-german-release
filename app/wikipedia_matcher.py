import re
import unicodedata


def normalize_title(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _candidate_title_cells(provider, headers: list[str]) -> list[int]:
    candidates = []
    for index, header in enumerate(headers):
        low = provider._normal_header(header)
        if any(token in low for token in ("titel", "originaltitel", "deutscher titel", "episodentitel")):
            candidates.append(index)
    return candidates


def _combined_headers(provider, grid: list[list[str]], header_flags: list[bool]) -> tuple[list[str], int]:
    header_indices: list[int] = []
    for index, is_header in enumerate(header_flags[:6]):
        if is_header:
            header_indices.append(index)
        elif header_indices:
            break
    if not header_indices:
        return [], 0

    width = max(len(grid[index]) for index in header_indices)
    headers = []
    for col in range(width):
        parts = []
        for row_index in header_indices:
            value = grid[row_index][col] if col < len(grid[row_index]) else ""
            if value and value not in parts:
                parts.append(value)
        headers.append(" ".join(parts))
    return headers, max(header_indices) + 1


async def match_episode_by_title(provider, mapping: dict, episode: dict) -> dict | None:
    """Conservatively match a Sonarr episode to a DE Wikipedia table row.

    Priority:
    1. Same season context + exact normalized title => high confidence.
    2. Exact normalized title unique across all inspected DE rows => medium confidence.

    TBA/empty titles and ambiguous matches are never accepted.
    """
    sonarr_title = (episode.get("title") or "").strip()
    normalized_target = normalize_title(sonarr_title)
    if not normalized_target or normalized_target in {"tba", "tbd", "unknown", "unbekannt"}:
        return None
    if len(normalized_target) < 4:
        return None

    dewiki_title = mapping.get("dewiki_title") if mapping else None
    if not dewiki_title:
        return None

    sonarr_season = episode.get("seasonNumber")
    matches: list[dict] = []

    for page_title in await provider.page_candidates(dewiki_title):
        try:
            html = await provider.page_html(page_title)
        except Exception:
            continue

        from bs4 import BeautifulSoup
        from urllib.parse import quote

        soup = BeautifulSoup(html, "html.parser")
        page_url = f"https://de.wikipedia.org/wiki/{quote(page_title.replace(' ', '_'))}"

        for table in soup.find_all("table"):
            grid, header_flags = provider._table_grid(table)
            if len(grid) < 2:
                continue

            headers, data_start = _combined_headers(provider, grid, header_flags)
            if not headers:
                continue

            de_scores = [provider._header_score(text, "de_date") for text in headers]
            if not de_scores or max(de_scores) == 0:
                continue
            de_col = de_scores.index(max(de_scores))

            title_cols = _candidate_title_cells(provider, headers)
            context_season = provider._season_from_context(table, page_title)

            season_scores = [provider._header_score(text, "season") for text in headers]
            season_col = season_scores.index(max(season_scores)) if season_scores and max(season_scores) else None

            for values in grid[data_start:]:
                if de_col >= len(values):
                    continue
                release_date = provider._date_to_iso(values[de_col])
                if not release_date:
                    continue

                row_season = context_season
                if row_season is None and season_col is not None and season_col < len(values):
                    row_season = provider._first_int(values[season_col])

                candidate_texts = []
                if title_cols:
                    candidate_texts = [values[i] for i in title_cols if i < len(values) and values[i]]
                if not candidate_texts:
                    candidate_texts = values

                matched_text = None
                for text in candidate_texts:
                    normalized = normalize_title(text)
                    if normalized == normalized_target:
                        matched_text = text
                        break
                    # Some Wikipedia cells contain original and German title together.
                    if normalized_target and re.search(rf"(?:^| )({re.escape(normalized_target)})(?: |$)", normalized):
                        matched_text = text
                        break

                if not matched_text:
                    continue

                matches.append({
                    "release_date": release_date,
                    "row_season": row_season,
                    "page_title": page_title,
                    "source_url": page_url,
                    "matched_title": matched_text,
                })

    if not matches:
        return None

    same_season = [m for m in matches if sonarr_season is not None and m.get("row_season") == sonarr_season]
    if len(same_season) == 1:
        match = same_season[0]
        return {
            "release_date": match["release_date"],
            "confidence": "high",
            "match_method": "season_title",
            "note": f"Deutsche Erstausstrahlung laut Wikipedia DE · Staffel + eindeutiger Episodentitel · {match['source_url']}",
            "source_url": match["source_url"],
            "page_title": match["page_title"],
        }

    # Only accept a title-only match when exactly one row across all pages matches.
    unique = {(m["release_date"], m["page_title"], m.get("row_season")) for m in matches}
    if len(unique) == 1:
        match = matches[0]
        return {
            "release_date": match["release_date"],
            "confidence": "medium",
            "match_method": "unique_title",
            "note": f"Deutsche Erstausstrahlung laut Wikipedia DE · eindeutiger Episodentitel · {match['source_url']}",
            "source_url": match["source_url"],
            "page_title": match["page_title"],
        }

    return None
