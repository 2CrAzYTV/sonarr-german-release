# Sonarr German Release

Begleitdienst für Sonarr zur Ermittlung und Anzeige deutscher Veröffentlichungs- und Streaming-Informationen.

## Aktueller Stand

Version 0.4.0 ist produktionsbereit und weiterhin absichtlich **read-only**:

- Verbindung zu Sonarr über API v3
- Serien und kommende Episoden aus Sonarr einlesen
- deutsche Episodendaten über kostenlose/keylose Quellen ergänzen
- Wikidata für exakte Serienzuordnung über IMDb-/TheTVDB-IDs
- Wikipedia DE für explizit gekennzeichnete deutsche/deutschsprachige Erstausstrahlungsdaten
- mehrstufiges Wikipedia↔Sonarr-Episodenmatching
- TVmaze DE Alternate Lists als weitere kostenlose Quelle
- fernsehserien.de als zusätzliche Quelle für deutsche Veröffentlichungsdaten
- Release-Typen werden ermittelt und in der WebUI dargestellt
- TMDB bleibt optional für Mapping und DE-Streaming-Verfügbarkeit
- SQLite-Datenbank für mehrere Quellen
- Quellenkonflikte werden angezeigt statt still überschrieben
- keine Änderungen an Sonarr
- keine kostenpflichtige IMDb-/AWS-Integration

## Quellen-Priorität

1. `manual_de` – manuell bestätigte deutsche Daten
2. `wikipedia_de` – explizite deutsche/deutschsprachige Erstausstrahlung aus Wikipedia-DE-Tabellen
3. `fernsehserien_de` – zusätzliche deutsche Episoden- und Veröffentlichungsdaten
4. `tvmaze_de` – explizite deutsche TVmaze Country-Premiere-Alternate-Lists
5. `streaming_de` – Deutschland-spezifische Streaming-Verfügbarkeit
6. `tmdb_de` – optionales TMDB Mapping/Fallback
7. `sonarr_tvdb` – letzter Fallback

Normale Weltpremieren werden weder von Wikipedia noch TVmaze als deutsches Datum interpretiert.

## Wikidata + Wikipedia DE

Der Wikimedia-Provider benötigt **keinen API-Key** und keine Registrierung.

Wikidata wird ausschließlich für exakte Zuordnungen verwendet:

- IMDb ID (`P345`)
- TheTVDB series ID (`P4835`)
- deutscher Wikipedia-Sitelink

Wikipedia DE wird ausschließlich über die offizielle MediaWiki Action API gelesen. Der Parser akzeptiert nur Episodentabellen, deren Spalten ausdrücklich eine deutsche/deutschsprachige Erstausstrahlung kennzeichnen.

### Episoden-Matching ab v0.3.3

Ein deutsches Datum wird nur übernommen, wenn ein konservativer Match gelingt:

1. exakte Staffel-/Episodennummer (`SxxExx`) → Confidence `very_high`
2. gleiche Staffel + eindeutig identischer Episodentitel → Confidence `high`
3. innerhalb der Serie eindeutig identischer Episodentitel → Confidence `medium`
4. bei mehreren möglichen Treffern oder `TBA` wird nichts übernommen

Damit können Unterschiede in der Episodennummerierung zwischen Wikipedia und Sonarr abgefangen werden, ohne unsichere Daten automatisch zu übernehmen.

Die WebUI verlinkt die jeweilige deutsche Wikipedia-Seite als Quelle.

### Wikimedia-Lizenzen

- strukturierte Wikidata-Daten: CC0
- Wikipedia-Texte: grundsätzlich CC BY-SA 4.0 und GFDL gemäß den Wikimedia-Nutzungsbedingungen

Das Projekt übernimmt keine längeren Wikipedia-Texte, sondern nur strukturierte Datumsangaben und Quellenlinks.

## TVmaze

TVmaze wird über die kostenlose öffentliche API ohne Schlüssel verwendet. Serien werden exakt über vorhandene IMDb-/TheTVDB-IDs zugeordnet. Als deutsche Releasedaten werden ausschließlich explizite DE-Country-Premiere-Alternate-Lists verwendet.

## TMDB API – optional

TMDB bleibt vollständig optional. Ohne `TMDB_API_TOKEN` läuft der Container normal weiter; der Provider wird lediglich als deaktiviert angezeigt.

Mit Token wird TMDB verwendet für:

- zusätzliche Serien-Mappings
- DE-Streaming-Verfügbarkeit über Watch Providers / JustWatch

Das normale TMDB-Episodenfeld `air_date` wird **nicht** als deutsches Veröffentlichungsdatum gespeichert.

Für die TMDB-Nutzung enthält die WebUI die vorgeschriebene Attribution sowie die JustWatch-Attribution. Persistierte TMDB-Mappings werden spätestens nach 180 Tagen erneut geprüft.

## Konfiguration

Für Unraid wird **keine `.env`-Datei verwendet**. Alle Einstellungen werden direkt als Container-Variablen gesetzt.

Basisvariablen:

- `SONARR_URL`
- `SONARR_API_KEY`
- `COUNTRY` = `DE`
- `LANGUAGE` = `de-DE`
- `TZ` = `Europe/Berlin`
- `DATABASE_PATH` = `/data/releases.sqlite3`
- `READ_ONLY` = `true`
- `PREFERRED_PROVIDER` = `wikipedia_de` empfohlen

Optional:

- `TMDB_API_TOKEN` – TMDB API Read Access Token

TVmaze, Wikidata und Wikipedia benötigen keine zusätzlichen Variablen oder Zugangsdaten.

## Unraid

- Container Name: `sonarr-german-release`
- Repository: `ghcr.io/2crazytv/sonarr-german-release:latest`
- WebUI Host-Port: `8789`
- Container-Port: `8788`
- Appdata: `/mnt/cache/appdata/sonarr-german-release/data`
- Container-Pfad: `/data`
- Restart Policy: `unless-stopped`

## Sonarr API-Key

Sonarr → Settings → General → Security → API Key

## Roadmap

### v0.4.0 – Production Ready (aktuell)

- bereinigte produktive WebUI (Entwicklungs-/Diagnoseansichten aus v0.3.x entfernt, siehe unten)
- stabile Quellenzuordnung und Release-Typ-Erkennung, verifiziert über einen mehrtägigen read-only-Teststand ohne Fehlzuordnungen
- stabile Verarbeitung von fernsehserien.de, Wikipedia DE und TVmaze DE
- nachvollziehbare Quellenkonflikte und Fallbacks (siehe "Quellen-Priorität" oben)
- Wikipedia-DE-Provider zu einer einzigen Implementierung konsolidiert (vorher als versionierte Unterklassen-Kette `wikimedia_v036`/`wikimedia_v037` geführt)
- ungenutzte Zweit-App aus `app/main.py` entfernt (Modul dient jetzt ausschließlich als gemeinsame Helper-Bibliothek für `app/main_cached.py`, den tatsächlich ausgelieferten Entrypoint)

Was sich gegenüber der Entwicklungsphase geändert hat: die WebUI zeigte bis v0.3.x zusätzlich granulare Parser-/Matcher-Diagnosen pro Serie ("Wikipedia Staffel-Diagnose", "fernsehserien.de Diagnose") sowie Zwischenzähler (Wikidata-Mappings, geprüfte Seiten/Tabellen, Matching-Methoden). Das war zum Verifizieren der Zuordnungslogik während der Entwicklung nötig, ist für den produktiven Betrieb aber nicht relevant und wurde entfernt. Die Sync-Logik selbst ist unverändert.

### v0.5.x – Erweiterte Sonarr-Integration

- Hybrid-Modus vorbereiten
- Sonarr-Suchen gezielt und kontrolliert freigeben
- Read-only weiterhin als sichere Standardbetriebsart beibehalten

### v1.0 – Optionale Automatisierung

- optional schreibender Sonarr-Betrieb
- kontrollierte Automatisierung auf Basis bestätigter deutscher Release-Daten
- Schutzmechanismen gegen unsichere oder widersprüchliche Quellen
- vollständige Produktionsdokumentation und stabile Upgrade-Pfade
