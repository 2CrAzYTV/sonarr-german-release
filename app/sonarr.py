import httpx
from .config import settings

class SonarrClient:
    def __init__(self):
        self.base = settings.sonarr_url.rstrip("/")
        self.headers = {"X-Api-Key": settings.sonarr_api_key}

    async def _get(self, path: str, params=None):
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base}/api/v3/{path.lstrip('/')}",
                headers=self.headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def system_status(self):
        return await self._get("system/status")

    async def series(self):
        return await self._get("series")

    async def calendar(self, start: str | None = None, end: str | None = None):
        params = {"includeSeries": "true", "includeEpisodeFile": "true"}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return await self._get("calendar", params=params)
