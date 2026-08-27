PROVIDER_PRIORITY = [
    "manual_de",
    "wikipedia_de",
    "fernsehserien_de",
    "tvmaze_de",
    "streaming_de",
    "tmdb_de",
    "sonarr_tvdb",
]

RELEASE_TYPE_PRIORITY = {
    "manual_de": 0,
    "streaming_de": 1,
    "tv_de": 2,
    "de_release": 3,
    "sonarr_fallback": 4,
}

CONFIDENCE_ORDER = {
    "very_high": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    None: 0,
}


def _release_day(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    return value[:10] if len(value) >= 10 else value


def _release_type(provider: str, data: dict) -> str:
    explicit = data.get("release_type")
    if explicit:
        return explicit
    if provider == "manual_de":
        return "manual_de"
    if provider in {"streaming_de", "tmdb_de"}:
        return "streaming_de"
    if provider in {"wikipedia_de", "tvmaze_de"}:
        return "tv_de"
    if provider == "sonarr_tvdb":
        return "sonarr_fallback"
    return "de_release"


def resolve_release(observations: dict) -> dict:
    """Resolve the earliest preferred German availability type.

    Manual data wins first. A verified German streaming premiere is preferred
    over a German TV premiere. Sonarr/TVDB remains the last fallback. Different
    dates across different release types are expected and are therefore not a
    conflict; a conflict is reported only when sources of the winning release
    type disagree on the calendar day.
    """
    valid = {
        provider: data
        for provider, data in (observations or {}).items()
        if data and data.get("release_date")
    }

    if not valid:
        return {
            "release_date": None,
            "release_type": None,
            "provider": None,
            "confidence": None,
            "conflict": False,
            "sources": [],
        }

    ranked = []
    for provider, data in valid.items():
        release_type = _release_type(provider, data)
        type_priority = RELEASE_TYPE_PRIORITY.get(release_type, 99)
        try:
            provider_priority = PROVIDER_PRIORITY.index(provider)
        except ValueError:
            provider_priority = len(PROVIDER_PRIORITY)
        ranked.append(
            (
                type_priority,
                provider_priority,
                -CONFIDENCE_ORDER.get(data.get("confidence"), 0),
                provider,
                release_type,
                data,
            )
        )

    ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    winning_type_priority, _, _, provider, winning_type, winner = ranked[0]

    comparable = [item for item in ranked if item[0] == winning_type_priority]
    release_days = {
        _release_day(item[5].get("release_date"))
        for item in comparable
        if _release_day(item[5].get("release_date"))
    }
    conflict = len(release_days) > 1

    return {
        "release_date": winner.get("release_date"),
        "release_type": winning_type,
        "provider": provider,
        "confidence": winner.get("confidence"),
        "conflict": conflict,
        "sources": [
            {
                "provider": item[3],
                "release_type": item[4],
                "release_date": item[5].get("release_date"),
                "confidence": item[5].get("confidence"),
                "note": item[5].get("note"),
            }
            for item in ranked
        ],
    }
