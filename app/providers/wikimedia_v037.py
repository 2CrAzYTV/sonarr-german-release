import re

from .wikimedia_v036 import WikimediaProvider as BaseWikimediaProvider, ProviderStatus


class WikimediaProvider(BaseWikimediaProvider):
    """v0.3.7: strict page-candidate filtering to avoid franchise bleed.

    Search results and linked episode pages may contain related shows from the
    same franchise. For example, a Dead City lookup must not ingest episode
    tables from the parent series The Walking Dead. Only pages that clearly
    retain the mapped German article title are accepted.
    """

    user_agent = (
        "SonarrGermanRelease/0.3.7 "
        "(https://github.com/2CrAzYTV/sonarr-german-release)"
    )

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            configured=True,
            active=True,
            note="Kostenlose Wikimedia APIs · striktes Staffel- und Seiten-Mapping v0.3.7 · kein API-Key",
        )

    @staticmethod
    def _normalize_page_title(value: str) -> str:
        value = value.casefold()
        value = re.sub(r"\s*\([^)]*\)\s*$", "", value).strip()
        value = value.replace("–", "-").replace("—", "-")
        value = re.sub(r"[^a-z0-9äöüß]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    async def page_candidates(self, title: str) -> list[str]:
        candidates = await super().page_candidates(title)
        base = self._normalize_page_title(title)
        base_words = [w for w in base.split() if len(w) >= 3]

        accepted: list[str] = []
        for candidate in candidates:
            normalized = self._normalize_page_title(candidate)

            # Always keep the mapped article itself.
            if candidate == title:
                accepted.append(candidate)
                continue

            # Strongest rule: full mapped title remains present in the page name.
            if base and base in normalized:
                accepted.append(candidate)
                continue

            # For short titles such as "Reacher", require every meaningful base
            # word to be present. This still allows "Reacher Episodenliste" but
            # blocks unrelated franchise pages.
            if base_words and all(word in normalized.split() for word in base_words):
                accepted.append(candidate)

        # Keep order stable and avoid duplicates.
        unique: list[str] = []
        for candidate in accepted:
            if candidate not in unique:
                unique.append(candidate)
        return unique[:12]
