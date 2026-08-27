import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import main as core

APP_VERSION = "0.3.8"
REFRESH_INTERVAL_SECONDS = 1800

app = FastAPI(title="Sonarr German Release", version=APP_VERSION)
core.templates.env.globals["app_version"] = APP_VERSION

_snapshot: dict | None = None
_snapshot_updated_at: str | None = None
_refresh_lock = asyncio.Lock()
_refreshing = False
_last_refresh_error: str | None = None


def _empty_wikipedia_sync() -> dict:
    return {
        "checked": 0,
        "wikidata_mapped": 0,
        "dewiki_pages": 0,
        "pages_checked": 0,
        "tables_seen": 0,
        "de_tables": 0,
        "dated_rows": 0,
        "matched_rows": 0,
        "release_dates": 0,
        "exact_matches": 0,
        "season_title_matches": 0,
        "combined_matches": 0,
        "unique_title_matches": 0,
        "coverage": [],
        "behind_count": 0,
        "errors": 0,
    }


async def build_snapshot() -> dict:
    status = await core.sonarr.system_status()
    series = await core.sonarr.series()
    core.sync_series_mappings(series)
    series_by_id = {item.get("id"): item for item in series if item.get("id")}

    tmdb_sync = await core.sync_tmdb_mappings()

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=45)
    episodes = await core.sonarr.calendar(start=now.isoformat(), end=end.isoformat())
    episodes.sort(key=lambda item: item.get("airDateUtc") or "9999")

    for episode in episodes:
        sonarr_date = episode.get("airDateUtc") or episode.get("airDate")
        core.upsert_episode_release(
            episode,
            provider="sonarr_tvdb",
            release_date=sonarr_date,
            confidence="low",
            note="Sonarr/TVDB fallback",
        )
        episode["tmdbSeriesId"] = core.get_tmdb_mapping(episode.get("seriesId"))

    wikipedia_sync = await core.enrich_wikipedia_de(episodes, series_by_id)
    tvmaze_sync = await core.enrich_tvmaze_de(episodes, series_by_id)
    streaming_sync = await core.enrich_streaming_de(episodes)

    episode_ids = [episode.get("id") for episode in episodes if episode.get("id")]
    release_data = core.episode_release_map(episode_ids)
    resolved = {
        episode_id: core.resolve_release(observations)
        for episode_id, observations in release_data.items()
    }

    return {
        "error": None,
        "status": status,
        "series": series,
        "episodes": episodes,
        "release_data": release_data,
        "resolved": resolved,
        "db": core.db_stats(),
        "mapping": core.mapping_stats(),
        "tmdb_sync": tmdb_sync,
        "streaming_sync": streaming_sync,
        "tvmaze_sync": tvmaze_sync,
        "wikipedia_sync": wikipedia_sync,
        "tmdb": core.tmdb.status(),
        "tvmaze": core.tvmaze.status(),
        "wikipedia": core.wikipedia.status(),
        "settings": core.settings,
    }


async def refresh_snapshot() -> None:
    global _snapshot, _snapshot_updated_at, _refreshing, _last_refresh_error

    if _refresh_lock.locked():
        return

    async with _refresh_lock:
        _refreshing = True
        try:
            fresh = await build_snapshot()
            _snapshot = fresh
            _snapshot_updated_at = datetime.now(timezone.utc).isoformat()
            _last_refresh_error = None
        except Exception as exc:
            _last_refresh_error = str(exc)[:300]
        finally:
            _refreshing = False


async def periodic_refresh() -> None:
    await refresh_snapshot()
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        await refresh_snapshot()


@app.on_event("startup")
async def startup() -> None:
    core.init_db()
    asyncio.create_task(periodic_refresh())


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "read_only": core.settings.read_only,
        "country": core.settings.country,
        "preferred_provider": core.settings.preferred_provider,
        "tmdb_api_configured": core.tmdb.status().configured,
        "tvmaze_active": core.tvmaze.status().active,
        "wikipedia_de_active": core.wikipedia.status().active,
        "snapshot_ready": _snapshot is not None,
        "snapshot_refreshing": _refreshing,
        "snapshot_updated_at": _snapshot_updated_at,
        "snapshot_error": _last_refresh_error,
    }


@app.get("/refresh")
async def refresh() -> RedirectResponse:
    if not _refresh_lock.locked():
        asyncio.create_task(refresh_snapshot())
    return RedirectResponse(url="/", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if _snapshot is None:
        message = "Die Daten werden im Hintergrund geladen. Die WebUI bleibt dabei erreichbar."
        if _last_refresh_error:
            message = f"Der letzte Hintergrund-Sync ist fehlgeschlagen: {_last_refresh_error}"
        return HTMLResponse(
            "<!doctype html><html lang='de'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<meta http-equiv='refresh' content='3'>"
            "<title>Sonarr German Release</title>"
            "<style>body{font-family:system-ui,sans-serif;background:#111827;color:#e5e7eb;margin:0}"
            "main{max-width:760px;margin:70px auto;padding:24px}.card{background:#1f2937;border:1px solid #374151;"
            "border-radius:12px;padding:22px}.muted{color:#9ca3af}a{color:#93c5fd}</style></head><body><main>"
            f"<div class='card'><h1>Sonarr German Release</h1><p>v{APP_VERSION}</p>"
            f"<p>{message}</p><p class='muted'>Automatische Aktualisierung alle 30 Minuten.</p>"
            "<p><a href='/refresh'>Jetzt erneut synchronisieren</a></p></div></main></body></html>",
            status_code=200,
        )

    context = dict(_snapshot)
    context["request"] = request
    context["snapshot_updated_at"] = _snapshot_updated_at
    context["snapshot_refreshing"] = _refreshing
    context["snapshot_error"] = _last_refresh_error
    return core.templates.TemplateResponse("index.html", context)
