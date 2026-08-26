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
    air_date as a German release date.

    The watch-provider endpoints are country-specific and are powered by
    JustWatch. They are used only as a Germany streaming-availability signal,
    never as an episode release timestamp.
    """

    name = "tmdb_de"

    def __init__(self):
        self._watch_cache: dict[tuple[int, int, str], dict] = {}

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
                note="TMDb API konfiguriert · Mapping + DE-Streaming aktiv",
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

    async def season_watch_providers(
        self,
        tmdb_series_id: int,
        season_number: int,
        country: str = "DE",
    ) -> dict:
        """Return country-specific streaming availability for one TV season.

        The result intentionally contains provider availability only. No date
        is inferred from this endpoint.
        """
        cache_key = (tmdb_series_id, season_number, country.upper())
        if cache_key in self._watch_cache:
            return self._watch_cache[cache_key]

        data = await self._get(
            f"tv/{tmdb_series_id}/season/{season_number}/watch/providers"
        )
        region = (data.get("results") or {}).get(country.upper()) or {}

        provider_groups = {}
        provider_names = []
        seen = set()

        for group in ("flatrate", "free", "ads", "rent", "buy"):
            names = []
            for item in region.get(group) or []:
                name = item.get("provider_name")
                if not name:
                    continue
                names.append(name)
                if name not in seen:
                    provider_names.append(name)
                    seen.add(name)
            if names:
                provider_groups[group] = names

        result = {
            "available": bool(provider_names),
            "providers": provider_names,
            "groups": provider_groups,
            "link": region.get("link"),
            "source": "JustWatch via TMDb",
            "country": country.upper(),
        }
        self._watch_cache[cache_key] = result
        return result
