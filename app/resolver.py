PROVIDER_PRIORITY = [
    "manual_de",
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


def resolve_release(observations: dict) -> dict:
    """Resolve the best release observation without hiding conflicts."""
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

    dates = {data.get("release_date") for data in valid.values()}
    conflict = len(dates) > 1

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
