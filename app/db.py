import sqlite3
from pathlib import Path
from .config import settings

SCHEMA = '''
CREATE TABLE IF NOT EXISTS episode_releases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sonarr_episode_id INTEGER NOT NULL UNIQUE,
    sonarr_series_id INTEGER NOT NULL,
    series_title TEXT NOT NULL,
    season_number INTEGER NOT NULL,
    episode_number INTEGER NOT NULL,
    episode_title TEXT,
    sonarr_air_date TEXT,
    german_release_date TEXT,
    source TEXT,
    confidence TEXT,
    checked_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS provider_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sonarr_series_id INTEGER NOT NULL UNIQUE,
    tvdb_id INTEGER,
    tmdb_id INTEGER,
    imdb_id TEXT,
    checked_at TEXT DEFAULT CURRENT_TIMESTAMP
);
'''

def init_db():
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)

def db_stats():
    with sqlite3.connect(settings.database_path) as conn:
        releases = conn.execute("SELECT COUNT(*) FROM episode_releases").fetchone()[0]
        mappings = conn.execute("SELECT COUNT(*) FROM provider_mappings").fetchone()[0]
    return {"releases": releases, "mappings": mappings}
