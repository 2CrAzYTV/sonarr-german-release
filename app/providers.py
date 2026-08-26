from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReleaseCandidate:
    provider: str
    release_date: Optional[str]
    confidence: str
    note: str = ""


PROVIDER_PRIORITY = [
    "imdb_de",
    "streaming_de",
    "tmdb_de",
    "sonarr_tvdb",
]


def pick_best(candidates: list[ReleaseCandidate]) -> Optional[ReleaseCandidate]:
    available = [c for c in candidates if c.release_date]
    if not available:
        return None

    rank = {name: index for index, name in enumerate(PROVIDER_PRIORITY)}
    return sorted(
        available,
        key=lambda c: (rank.get(c.provider, 999), c.release_date),
    )[0]


def detect_conflict(candidates: list[ReleaseCandidate]) -> bool:
    dates = {c.release_date for c in candidates if c.release_date}
    return len(dates) > 1


def provider_label(provider: str) -> str:
    return {
        "imdb_de": "IMDb DE",
        "streaming_de": "Streaming DE",
        "tmdb_de": "TMDb DE",
        "sonarr_tvdb": "Sonarr/TVDB",
    }.get(provider, provider)
