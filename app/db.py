import sqlite3
from pathlib import Path
from .config import settings

SCHEMA = '''
CREATE TABLE IF NOT EXISTS episode_releases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sonarr_episode_id INTEGER NOT NULL,
    sonarr_series_id INTEGER NOT NULL,
    series_title TEXT NOT NULL,
    season_number INTEGER NOT NULL,
    episode_number INTEGER NOT NULL,
    episode_title TEXT,
    provider TEXT NOT NULL,
    release_date TEXT,
    country TEXT NOT NULL DEFAULT 'DE',
    confidence TEXT,
    note TEXT,
    checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(sonarr_episode_id, provider)
);

CREATE TABLE IF NOT EXISTS provider_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sonarr_series_id INTEGER NOT NULL UNIQUE,
    series_title TEXT,
    tvdb_id INTEGER,
    tmdb_id INTEGER,
    imdb_id TEXT,
    checked_at TEXT DEFAULT CURRENT_TIMESTAMP
);
'''


def _connect():
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(provider_mappings)")}
        if "series_title" not in columns:
            conn.execute("ALTER TABLE provider_mappings ADD COLUMN series_title TEXT")


def sync_series_mappings(series_list: list[dict]) -> dict:
    mapped = 0
    missing_imdb = 0
    with _connect() as conn:
        for item in series_list:
            sonarr_id = item.get("id")
            if not sonarr_id:
                continue
            imdb_id = item.get("imdbId") or None
            if imdb_id:
                mapped += 1
            else:
                missing_imdb += 1
            conn.execute(
                '''
                INSERT INTO provider_mappings
                    (sonarr_series_id, series_title, tvdb_id, tmdb_id, imdb_id, checked_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(sonarr_series_id) DO UPDATE SET
                    series_title=excluded.series_title,
                    tvdb_id=excluded.tvdb_id,
                    imdb_id=excluded.imdb_id,
                    checked_at=CURRENT_TIMESTAMP
                ''',
                (
                    sonarr_id,
                    item.get("title"),
                    item.get("tvdbId"),
                    item.get("tmdbId"),
                    imdb_id,
                ),
            )
    return {"mapped": mapped, "missing_imdb": missing_imdb}


def mapping_stats():
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM provider_mappings").fetchone()[0]
        imdb = conn.execute(
            "SELECT COUNT(*) FROM provider_mappings WHERE imdb_id IS NOT NULL AND imdb_id != ''"
        ).fetchone()[0]
    return {"total": total, "imdb": imdb, "missing_imdb": max(total - imdb, 0)}


def db_stats():
    with _connect() as conn:
        releases = conn.execute("SELECT COUNT(*) FROM episode_releases").fetchone()[0]
        mappings = conn.execute("SELECT COUNT(*) FROM provider_mappings").fetchone()[0]
        providers = conn.execute("SELECT COUNT(DISTINCT provider) FROM episode_releases").fetchone()[0]
    return {"releases": releases, "mappings": mappings, "providers": providers}
