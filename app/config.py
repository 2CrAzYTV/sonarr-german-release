from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    sonarr_url: str
    sonarr_api_key: str
    country: str = "DE"
    language: str = "de-DE"
    tz: str = "Europe/Berlin"
    database_path: str = "/data/releases.sqlite3"
    read_only: bool = True
    preferred_provider: str = "imdb_de"

    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
