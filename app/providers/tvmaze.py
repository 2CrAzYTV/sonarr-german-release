from dataclasses import dataclass
import asyncio

import httpx

from ..config import settings


@dataclass
class ProviderStatus:
    name: str
    configured: bool
    active: bool
    note: str


class TvmazeProvider:
    """Free/public TVmaze provider for country-specific German airdates.

    Only country-specific alternate lists for DE are treated as German release
    observations. Regular/world-premiere episode dates are never promoted to a
    German release date.
    """

    name = "tvmaze_de"

    def __init__(self):
        self._show_cache: dict[tuple[str, str], dict | None] = {}
        self._alternate_cache: dict[int, list[dict]] = {}

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            configured=True,
            active=True,
            note="Kostenlose öffentliche API · kein API-Key erforderlich",
        )

    async def _get(self, path: str, params: dict | None = None):
        url = f"{settings.tvmaze_base_url.rstrip('/')}/{path.lstrip('/')}"
        last_error = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                    response = await client.get(url, params=params)
                    if response.status_code == 404:
                        return None
                    if response.status_code == 429:
                        await asyncio.sleep(1.0 + attempt)
                        continue
                    response.raise_for_status()
                    return response.json()
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.5 + attempt)
        if last_error:
            raise last_error
        return None

    async def lookup_show(
        self,
        imdb_id: str | None = None,
        tvdb_id: int | None = None,
    ) -> dict | None:
        """Resolve an exact TVmaze show using an existing external ID."""
        if imdb_id:
            key = ("imdb", str(imdb_id))
            if key not in self._show_cache:
                self._show_cache[key] = await self._get(
                    "lookup/shows", params={"imdb": imdb_id}
                )
            if self._show_cache[key]:
                return self._show_cache[key]

        if tvdb_id:
            key = ("thetvdb", str(tvdb_id))
            if key not in self._show_cache:
                self._show_cache[key] = await self._get(
                    "lookup/shows", params={"thetvdb": tvdb_id}
                )
            return self._show_cache[key]

        return None

    async def german_alternate_lists(self, tvmaze_show_id: int) -> list[dict]:
        """Return only alternate lists explicitly tied to Germany (DE)."""
        if tvmaze_show_id in self._alternate_cache:
            return self._alternate_cache[tvmaze_show_id]

        lists = await self._get(f"shows/{tvmaze_show_id}/alternatelists") or []
        result = []
        for item in lists:
            country = item.get("country") or {}
            if str(country.get("code") or "").upper() == settings.country.upper():
                result.append(item)

        self._alternate_cache[tvmaze_show_id] = result
        return result

    async def german_episode_dates(self, tvmaze_show_id: int) -> dict[tuple[int, int], dict]:
        """Return DE country-premiere dates keyed by original S/E numbering."""
        result: dict[tuple[int, int], dict] = {}

        for alternate_list in await self.german_alternate_lists(tvmaze_show_id):
            list_id = alternate_list.get("id")
            if not list_id:
                continue

            episodes = await self._get(
                f"alternatelists/{list_id}/alternateepisodes",
                params={"embed": "episodes"},
            ) or []

            for item in episodes:
                embedded = (item.get("_embedded") or {}).get("episode") or {}
                season = embedded.get("season")
                number = embedded.get("number")

                # Fall back to alternate numbering only when original episode
                # information is not embedded.
                if season is None:
                    season = item.get("season")
                if number is None:
                    number = item.get("number")
                if season is None or number is None:
                    continue

                airdate = item.get("airdate")
                airtime = item.get("airtime")
                airstamp = item.get("airstamp")
                if airstamp:
                    release_date = airstamp
                    time_known = True
                elif airdate and airtime:
                    release_date = f"{airdate}T{airtime}:00"
                    time_known = True
                elif airdate:
                    release_date = f"{airdate}T00:00:00"
                    time_known = False
                else:
                    continue

                key = (int(season), int(number))
                observation = {
                    "release_date": release_date,
                    "confidence": "high" if time_known else "medium",
                    "note": (
                        "TVmaze DE Country Premiere"
                        if time_known
                        else "TVmaze DE Country Premiere · Uhrzeit nicht gemeldet"
                    ),
                    "alternate_list_id": list_id,
                    "alternate_list_name": alternate_list.get("name"),
                }

                # Keep the first explicit DE list for a matching episode.
                result.setdefault(key, observation)

        return result
