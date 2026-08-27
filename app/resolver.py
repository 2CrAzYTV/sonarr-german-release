PROVIDER_PRIORITY = [
    "manual_de",
    "wikipedia_de",
    "fernsehserien_de",
    "tvmaze_de",
    "streaming_de",
    "tmdb_de",
    "sonarr_tvdb",
]

CONFIDENCE_ORDER = {
    "very_high": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    None: 0,
}


def _release_day(value: str | None) -> str | None:
    """Return the calendar day of a release observation.

    Some providers, such as fernsehserien.de, publish a release date without a
    clock time, while Sonarr often provides an exact UTC timestamp. For the
    German-release resolver, observations on the same calendar day agree.
    """
    if not value:
        return None
    value = value.strip()
    return value[:10] if len(value) >= 10 else value


def resolve_release(observations: dict) -> dict:
    """Resolve the best release observation without hiding real date conflicts."""
    valid = {
        provider: data
        for provider, data in (observations or {}).items()
        if data and data.get("release_date")
    }

    if not valid:
        return {
            "release_date": None,
            "provider": None,
            "confidence": None,
            "conflict": False,
            "sources": [],
        }

    release_days = {
        _release_day(data.get("release_date"))
        for data in valid.values()
        if _release_day(data.get("release_date"))
    }
    conflict = len(release_days) > 1

    ranked = []
    for provider, data in valid.items():
        try:
            priority = PROVIDER_PRIORITY.index(provider)
        except ValueError:
            priority = len(PROVIDER_PRIORITY)
        ranked.append(
            (
                priority,
                -CONFIDENCE_ORDER.get(data.get("confidence"), 0),
                provider,
                data,
            )
        )

    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    _, _, provider, winner = ranked[0]

    return {
        "release_date": winner.get("release_date"),
        "provider": provider,
        "confidence": winner.get("confidence"),
        "conflict": conflict,
        "sources": [
            {
                "provider": item[2],
                "release_date": item[3].get("release_date"),
                "confidence": item[3].get("confidence"),
                "note": item[3].get("note"),
            }
            for item in ranked
        ],
    }
