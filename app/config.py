from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    sonarr_url: str
    sonarr_api_key: str
    country: str = "DE"
    language: str = "de-DE"
    tz: str = "Europe/Berlin"
    database_path: str = "/data/releases.sqlite3"
    read_only: bool = True
    preferred_provider: str = "tmdb_de"

    # TMDB API Read Access Token.
    tmdb_api_token: str | None = None
    tmdb_base_url: str = "https://api.themoviedb.org/3"

    model_config = SettingsConfigDict(extra="ignore")

    @property
    def tmdb_api_configured(self) -> bool:
        return bool(self.tmdb_api_token)


settings = Settings()
