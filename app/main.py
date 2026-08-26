from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import settings
from .db import (
    init_db,
    db_stats,
    mapping_stats,
    sync_series_mappings,
    get_imdb_mapping,
    upsert_episode_release,
    episode_release_map,
)
from .providers import ImdbProvider
from .sonarr import SonarrClient

app = FastAPI(title="Sonarr German Release", version="0.2.2")
templates = Jinja2Templates(directory="app/templates")
sonarr = SonarrClient()
imdb = ImdbProvider()


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
async def health():
    provider = imdb.status()
    return {
        "status": "ok",
        "version": "0.2.2",
        "read_only": settings.read_only,
        "country": settings.country,
        "preferred_provider": settings.preferred_provider,
        "imdb_api_configured": provider.configured,
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    error = None
    status = None
    series = []
    episodes = []
    mapping_sync = {"mapped": 0, "missing_imdb": 0}
    release_data = {}

    try:
        status = await sonarr.system_status()
        series = await sonarr.series()
        mapping_sync = sync_series_mappings(series)

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
            episode["imdbSeriesId"] = get_imdb_mapping(episode.get("seriesId"))

        release_data = episode_release_map(
            [episode.get("id") for episode in episodes if episode.get("id")]
        )
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
            "db": db_stats(),
            "mapping": mapping_stats(),
            "mapping_sync": mapping_sync,
            "imdb": imdb.status(),
            "settings": settings,
        },
    )
