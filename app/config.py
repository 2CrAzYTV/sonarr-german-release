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

    # Optional official IMDb API via AWS Data Exchange.
    imdb_api_endpoint: str | None = None
    imdb_aws_region: str = "us-east-1"
    imdb_aws_access_key_id: str | None = None
    imdb_aws_secret_access_key: str | None = None
    imdb_aws_session_token: str | None = None

    # Optional TMDb API Read Access Token. Used for mapping/fallback checks only.
    tmdb_api_token: str | None = None
    tmdb_base_url: str = "https://api.themoviedb.org/3"

    model_config = SettingsConfigDict(extra="ignore")

    @property
    def imdb_api_configured(self) -> bool:
        return bool(
            self.imdb_api_endpoint
            and self.imdb_aws_access_key_id
            and self.imdb_aws_secret_access_key
        )

    @property
    def tmdb_api_configured(self) -> bool:
        return bool(self.tmdb_api_token)


settings = Settings()
