from dataclasses import dataclass
import httpx

from ..config import settings


@dataclass
class ProviderStatus:
    name: str
    configured: bool
    active: bool
    note: str


class TmdbProvider:
    """TMDb mapping/fallback provider.

    TMDb does not expose a Germany-specific release-date endpoint for TV
    episodes. Therefore this provider must not label the generic episode
    air_date as a German release date. It is currently used for identifier
    mapping and future corroboration only.
    """

    name = "tmdb_de"

    @property
    def headers(self) -> dict[str, str]:
        if not settings.tmdb_api_token:
            return {}
        return {
            "Authorization": f"Bearer {settings.tmdb_api_token}",
            "accept": "application/json",
        }

    def status(self) -> ProviderStatus:
        if settings.tmdb_api_configured:
            return ProviderStatus(
                name=self.name,
                configured=True,
                active=True,
                note="TMDb API konfiguriert · Mapping/Fallback aktiv",
            )
        return ProviderStatus(
            name=self.name,
            configured=False,
            active=False,
            note="TMDb API Read Access Token fehlt",
        )

    async def _get(self, path: str, params: dict | None = None):
        if not settings.tmdb_api_configured:
            raise RuntimeError("TMDb API ist nicht konfiguriert")
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{settings.tmdb_base_url.rstrip('/')}/{path.lstrip('/')}",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def find_series_id(
        self,
        imdb_id: str | None = None,
        tvdb_id: int | None = None,
    ) -> int | None:
        """Resolve a TMDb TV series id from an external identifier."""
        if imdb_id:
            data = await self._get(
                f"find/{imdb_id}",
                params={"external_source": "imdb_id", "language": settings.language},
            )
            results = data.get("tv_results") or []
            if results:
                return results[0].get("id")

        if tvdb_id:
            data = await self._get(
                f"find/{tvdb_id}",
                params={"external_source": "tvdb_id", "language": settings.language},
            )
            results = data.get("tv_results") or []
            if results:
                return results[0].get("id")

        return None

    async def episode_details(
        self,
        tmdb_series_id: int,
        season_number: int,
        episode_number: int,
    ) -> dict:
        """Fetch episode metadata without interpreting air_date as DE release."""
        return await self._get(
            f"tv/{tmdb_series_id}/season/{season_number}/episode/{episode_number}",
            params={"language": settings.language},
        )
