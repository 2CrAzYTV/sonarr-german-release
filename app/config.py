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

    # Official IMDb API via AWS Data Exchange.
    imdb_aws_region: str = "us-east-1"
    imdb_aws_access_key_id: str | None = None
    imdb_aws_secret_access_key: str | None = None
    imdb_aws_session_token: str | None = None
    imdb_data_set_id: str | None = None
    imdb_revision_id: str | None = None
    imdb_asset_id: str | None = None
    imdb_api_key: str | None = None

    # Optional TMDb API Read Access Token. Used for mapping/fallback checks only.
    tmdb_api_token: str | None = None
    tmdb_base_url: str = "https://api.themoviedb.org/3"

    model_config = SettingsConfigDict(extra="ignore")

    @property
    def imdb_missing_settings(self) -> list[str]:
        required = {
            "IMDB_AWS_ACCESS_KEY_ID": self.imdb_aws_access_key_id,
            "IMDB_AWS_SECRET_ACCESS_KEY": self.imdb_aws_secret_access_key,
            "IMDB_DATA_SET_ID": self.imdb_data_set_id,
            "IMDB_REVISION_ID": self.imdb_revision_id,
            "IMDB_ASSET_ID": self.imdb_asset_id,
            "IMDB_API_KEY": self.imdb_api_key,
        }
        return [name for name, value in required.items() if not value]

    @property
    def imdb_api_configured(self) -> bool:
        return not self.imdb_missing_settings

    @property
    def tmdb_api_configured(self) -> bool:
        return bool(self.tmdb_api_token)


settings = Settings()
