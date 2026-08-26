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

    model_config = SettingsConfigDict(extra="ignore")

    @property
    def imdb_api_configured(self) -> bool:
        return bool(
            self.imdb_api_endpoint
            and self.imdb_aws_access_key_id
            and self.imdb_aws_secret_access_key
        )


settings = Settings()
