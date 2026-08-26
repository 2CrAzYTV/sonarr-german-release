from dataclasses import dataclass
from . import __all__  # noqa: F401
from ..config import settings


@dataclass
class ProviderStatus:
    name: str
    configured: bool
    active: bool
    note: str


class ImdbProvider:
    """Official IMDb API provider scaffold.

    Uses IMDb's AWS Data Exchange GraphQL API when credentials are configured.
    No webpage scraping is performed.
    """

    name = "imdb_de"

    def status(self) -> ProviderStatus:
        if settings.imdb_api_configured:
            return ProviderStatus(
                name=self.name,
                configured=True,
                active=True,
                note="Offizielle IMDb API konfiguriert",
            )
        return ProviderStatus(
            name=self.name,
            configured=False,
            active=False,
            note="IMDb API Zugang noch nicht konfiguriert",
        )
