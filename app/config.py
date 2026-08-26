from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    sonarr_url: str
    sonarr_api_key: str
    country: str = "DE"
    language: str = "de-DE"
    tz: str = "Europe/Berlin"
    database_path: str = "/data/releases.sqlite3"
    read_only: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
