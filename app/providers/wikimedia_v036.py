from .wikimedia import WikimediaProvider as BaseWikimediaProvider, ProviderStatus


class WikimediaProvider(BaseWikimediaProvider):
    """v0.3.6: stricter season/episode column classification.

    Wikipedia episode tables often use grouped headers such as "Staffel" above
    columns like "Nr. (ges.)" and "Nr. (St.)". The older parser could combine
    those header rows and accidentally treat an episode-number column as a
    season column. This subclass only accepts dedicated, unambiguous season
    headers as season columns.
    """

    user_agent = (
        "SonarrGermanRelease/0.3.6 "
        "(https://github.com/2CrAzYTV/sonarr-german-release)"
    )

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            configured=True,
            active=True,
            note="Kostenlose Wikimedia APIs · striktes Staffel-Mapping v0.3.6 · kein API-Key",
        )

    @classmethod
    def _header_score(cls, text: str, kind: str) -> int:
        low = cls._normal_header(text)

        if kind == "season":
            # Reject grouped/combined headers that also describe episode or
            # total-number columns. These were the source of false seasons.
            forbidden = (
                "folge",
                "episode",
                "gesamt",
                "nr. st",
                "nr st",
                "in staffel",
                "staffelfolge",
            )
            if any(token in low for token in forbidden):
                return 0

            dedicated = {
                "staffel",
                "staffel nr.",
                "staffel nr",
                "staffelnr.",
                "staffelnr",
                "staffelnummer",
                "season",
                "season nr.",
                "season nr",
            }
            if low in dedicated:
                return 100

            # A header may contain harmless formatting text, but it must still
            # be unmistakably a season field and not merely a grouped parent.
            if low.startswith("staffel ") and len(low.split()) <= 2:
                return 90
            if low.startswith("season ") and len(low.split()) <= 2:
                return 90
            return 0

        if kind == "episode":
            # A dedicated season column must never become the episode column.
            if low in {
                "staffel",
                "staffel nr.",
                "staffel nr",
                "staffelnr.",
                "staffelnr",
                "staffelnummer",
                "season",
            }:
                return 0
            if "nr. staffel" in low or "nr staffel" in low:
                return 0

        return super()._header_score(text, kind)
