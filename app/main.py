from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import settings
from .db import (
    init_db,
    db_stats,
    mapping_stats,
    sync_series_mappings,
    get_tmdb_mapping,
    series_missing_tmdb_mapping,
    set_tmdb_mapping,
    upsert_episode_release,
    episode_release_map,
)
from .providers import TmdbProvider
from .resolver import resolve_release
from .sonarr import SonarrClient

app = FastAPI(title="Sonarr German Release", version="0.2.9")
templates = Jinja2Templates(directory="app/templates")
sonarr = SonarrClient()
tmdb = TmdbProvider()


def format_datetime_de(value: str | None) -> str:
    if not value:
        return "-"

    try:
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is not None:
            dt = dt.astimezone(ZoneInfo(settings.tz))

        return dt.strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        return value


templates.env.globals["format_datetime_de"] = format_datetime_de


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
async def health():
    tmdb_status = tmdb.status()
    return {
        "status": "ok",
        "version": "0.2.9",
        "read_only": settings.read_only,
        "country": settings.country,
        "preferred_provider": settings.preferred_provider,
        "tmdb_api_configured": tmdb_status.configured,
    }


async def sync_tmdb_mappings() -> dict:
    if not settings.tmdb_api_configured:
        return {"checked": 0, "mapped": 0, "errors": 0}

    checked = 0
    mapped = 0
    errors = 0

    for item in series_missing_tmdb_mapping(limit=500):
        checked += 1
        try:
            tmdb_id = await tmdb.find_series_id(
                imdb_id=item.get("imdb_id"),
                tvdb_id=item.get("tvdb_id"),
            )
            if tmdb_id:
                set_tmdb_mapping(item["sonarr_series_id"], tmdb_id)
                mapped += 1
        except Exception:
            errors += 1

    return {"checked": checked, "mapped": mapped, "errors": errors}


async def enrich_streaming_de(episodes: list[dict]) -> dict:
    """Attach DE streaming availability to episodes on a season basis."""
    if not settings.tmdb_api_configured:
        return {"checked": 0, "available": 0, "errors": 0}

    checked = 0
    available = 0
    errors = 0
    season_results: dict[tuple[int, int], dict] = {}

    for episode in episodes:
        tmdb_id = episode.get("tmdbSeriesId")
        season_number = episode.get("seasonNumber")
        if not tmdb_id or season_number is None:
            continue
        key = (tmdb_id, season_number)
        if key in season_results:
            continue

        checked += 1
        try:
            result = await tmdb.season_watch_providers(
                tmdb_id,
                season_number,
                country=settings.country,
            )
            season_results[key] = result
            if result.get("available"):
                available += 1
        except Exception as exc:
            errors += 1
            season_results[key] = {
                "available": False,
                "providers": [],
                "source": "JustWatch via TMDB",
                "error": str(exc),
            }

    for episode in episodes:
        key = (episode.get("tmdbSeriesId"), episode.get("seasonNumber"))
        episode["streamingDE"] = season_results.get(key)

    return {"checked": checked, "available": available, "errors": errors}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    error = None
    status = None
    series = []
    episodes = []
    tmdb_sync = {"checked": 0, "mapped": 0, "errors": 0}
    streaming_sync = {"checked": 0, "available": 0, "errors": 0}
    release_data = {}
    resolved = {}

    try:
        status = await sonarr.system_status()
        series = await sonarr.series()
        sync_series_mappings(series)
        tmdb_sync = await sync_tmdb_mappings()

        now = datetime.now(timezone.utc)
        end = now + timedelta(days=45)
        episodes = await sonarr.calendar(
            start=now.isoformat(),
            end=end.isoformat(),
        )
        episodes.sort(key=lambda item: item.get("airDateUtc") or "9999")

        for episode in episodes:
            sonarr_date = episode.get("airDateUtc") or episode.get("airDate")
            upsert_episode_release(
                episode,
                provider="sonarr_tvdb",
                release_date=sonarr_date,
                confidence="low",
                note="Sonarr/TVDB fallback",
            )
            episode["tmdbSeriesId"] = get_tmdb_mapping(episode.get("seriesId"))

        streaming_sync = await enrich_streaming_de(episodes)

        episode_ids = [episode.get("id") for episode in episodes if episode.get("id")]
        release_data = episode_release_map(episode_ids)
        resolved = {
            episode_id: resolve_release(observations)
            for episode_id, observations in release_data.items()
        }
    except Exception as exc:
        error = str(exc)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "error": error,
            "status": status,
            "series": series,
            "episodes": episodes,
            "release_data": release_data,
            "resolved": resolved,
            "db": db_stats(),
            "mapping": mapping_stats(),
            "tmdb_sync": tmdb_sync,
            "streaming_sync": streaming_sync,
            "tmdb": tmdb.status(),
            "settings": settings,
        },
    )
