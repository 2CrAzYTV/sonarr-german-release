from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import settings
from .db import init_db, db_stats
from .sonarr import SonarrClient

app = FastAPI(title="Sonarr German Release", version="0.1.1")
templates = Jinja2Templates(directory="app/templates")
sonarr = SonarrClient()

@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.1",
        "read_only": settings.read_only,
        "country": settings.country,
    }

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    error = None
    status = None
    series = []
    episodes = []

    try:
        status = await sonarr.system_status()
        series = await sonarr.series()

        now = datetime.now(timezone.utc)
        end = now + timedelta(days=45)
        episodes = await sonarr.calendar(
            start=now.isoformat(),
            end=end.isoformat(),
        )
        episodes.sort(key=lambda item: item.get("airDateUtc") or "9999")
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
            "db": db_stats(),
            "settings": settings,
        },
    )
