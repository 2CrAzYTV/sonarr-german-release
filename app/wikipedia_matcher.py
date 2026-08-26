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


def _title_columns(provider, headers: list[str]) -> tuple[list[int], list[int]]:
    original = []
    german = []
    for index, header in enumerate(headers):
        low = provider._normal_header(header)
        if any(token in low for token in ("originaltitel", "original title", "englischer titel", "engl. titel")):
            original.append(index)
        elif any(token in low for token in ("deutscher titel", "deutscher episodentitel", "dt. titel", "titel de")):
            german.append(index)
        elif "titel" in low or "episodentitel" in low:
            # Generic title columns may contain either the original or translated title.
            original.append(index)
            german.append(index)
    return original, german


def _number_columns(provider, headers: list[str]) -> tuple[int | None, int | None, int | None]:
    season_col = None
    episode_col = None
    total_col = None

    season_scores = [provider._header_score(text, "season") for text in headers]
    if season_scores and max(season_scores):
        season_col = season_scores.index(max(season_scores))

    ep_scores = [provider._header_score(text, "episode") for text in headers]
    if ep_scores and max(ep_scores):
        episode_col = ep_scores.index(max(ep_scores))

    for index, header in enumerate(headers):
        low = provider._normal_header(header)
        if any(token in low for token in (
            "nr. ges", "nr ges", "gesamtfolge", "gesamt folge", "gesamt nr",
            "nr. gesamt", "episode gesamt", "folge gesamt", "nr. serie",
        )):
            total_col = index
            break

    if episode_col is None:
        nr_cols = [i for i, h in enumerate(headers) if re.search(r"\bnr\.?\b", provider._normal_header(h))]
        if len(nr_cols) >= 2:
            total_col = total_col if total_col is not None else nr_cols[0]
            episode_col = nr_cols[1]
        elif len(nr_cols) == 1:
            episode_col = nr_cols[0]

    return season_col, episode_col, total_col


def _title_match(target: str, candidate: str) -> bool:
    normalized = normalize_title(candidate)
    if not normalized:
        return False
    if normalized == target:
        return True
    # Allow a cell such as "Plum Out of Luck / Vom Pech verfolgt" to contain the exact title.
    return bool(re.search(rf"(?:^| ){re.escape(target)}(?: |$)", normalized))


async def match_episode_by_title(provider, mapping: dict, episode: dict) -> dict | None:
    """Conservatively match a Sonarr episode to a German Wikipedia DE row.

    Matching priority:
    1. Same season + exact original/generic title.
    2. Exact title + matching episode number, even when season numbering differs.
    3. Exact title unique across all inspected DE rows.
    4. Matching season episode number + total/absolute number where available.

    Ambiguous matches and placeholder titles are never accepted.
    """
    sonarr_title = (episode.get("title") or "").strip()
    target = normalize_title(sonarr_title)
    if not target or target in {"tba", "tbd", "unknown", "unbekannt"} or len(target) < 4:
        return None

    dewiki_title = mapping.get("dewiki_title") if mapping else None
    if not dewiki_title:
        return None

    sonarr_season = episode.get("seasonNumber")
    sonarr_episode = episode.get("episodeNumber")
    sonarr_absolute = episode.get("absoluteEpisodeNumber")
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

            original_cols, german_cols = _title_columns(provider, headers)
            season_col, episode_col, total_col = _number_columns(provider, headers)
            context_season = provider._season_from_context(table, page_title)

            for values in grid[data_start:]:
                if de_col >= len(values):
                    continue
                release_date = provider._date_to_iso(values[de_col])
                if not release_date:
                    continue

                row_season = context_season
                if row_season is None and season_col is not None and season_col < len(values):
                    row_season = provider._first_int(values[season_col])

                row_episode = provider._first_int(values[episode_col]) if episode_col is not None and episode_col < len(values) else None
                row_total = provider._first_int(values[total_col]) if total_col is not None and total_col < len(values) else None

                title_cells = []
                seen = set()
                for idx in original_cols + german_cols:
                    if idx < len(values) and values[idx] and values[idx] not in seen:
                        seen.add(values[idx])
                        title_cells.append(values[idx])

                matched_title = next((text for text in title_cells if _title_match(target, text)), None)
                if not matched_title:
                    continue

                matches.append({
                    "release_date": release_date,
                    "row_season": row_season,
                    "row_episode": row_episode,
                    "row_total": row_total,
                    "page_title": page_title,
                    "source_url": page_url,
                    "matched_title": matched_title,
                })

    if not matches:
        return None

    def observation(match: dict, confidence: str, method: str, label: str) -> dict:
        return {
            "release_date": match["release_date"],
            "confidence": confidence,
            "match_method": method,
            "note": f"Deutsche Erstausstrahlung laut Wikipedia DE · {label} · {match['source_url']}",
            "source_url": match["source_url"],
            "page_title": match["page_title"],
        }

    # Strongest title-based match: same season and same episode number when both exist.
    exact_identity = [
        m for m in matches
        if sonarr_season is not None and sonarr_episode is not None
        and m.get("row_season") == sonarr_season and m.get("row_episode") == sonarr_episode
    ]
    if len(exact_identity) == 1:
        return observation(exact_identity[0], "very_high", "season_episode_title", "Staffel + Folge + Episodentitel")

    same_season = [m for m in matches if sonarr_season is not None and m.get("row_season") == sonarr_season]
    if len(same_season) == 1:
        return observation(same_season[0], "high", "season_title", "Staffel + eindeutiger Episodentitel")

    same_episode_number = [m for m in matches if sonarr_episode is not None and m.get("row_episode") == sonarr_episode]
    if len(same_episode_number) == 1:
        return observation(same_episode_number[0], "high", "episode_title", "Folgenummer + eindeutiger Episodentitel")

    if sonarr_absolute is not None:
        same_absolute = [m for m in matches if m.get("row_total") == sonarr_absolute]
        if len(same_absolute) == 1:
            return observation(same_absolute[0], "high", "absolute_title", "Gesamtfolgennummer + Episodentitel")

    # Finally accept title-only only when exactly one semantic row exists.
    unique = {
        (m["release_date"], m["page_title"], m.get("row_season"), m.get("row_episode"), m.get("row_total"))
        for m in matches
    }
    if len(unique) == 1:
        return observation(matches[0], "medium", "unique_title", "serienweit eindeutiger Episodentitel")

    return None
