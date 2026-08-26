# Sonarr German Release

Begleitdienst für Sonarr zur Ermittlung und Anzeige deutscher Veröffentlichungs- und Streaming-Informationen.

## Aktueller Stand

Version 0.3.3 ist absichtlich **read-only**:

- Verbindung zu Sonarr über API v3
- Serien und kommende Episoden aus Sonarr einlesen
- deutsche Episodendaten über kostenlose/keylose Quellen ergänzen
- Wikidata für exakte Serienzuordnung über IMDb-/TheTVDB-IDs
- Wikipedia DE für explizit gekennzeichnete deutsche/deutschsprachige Erstausstrahlungsdaten
- mehrstufiges Wikipedia↔Sonarr-Episodenmatching
- TVmaze DE Alternate Lists als weitere kostenlose Quelle
- TMDB bleibt optional für Mapping und DE-Streaming-Verfügbarkeit
- SQLite-Datenbank für mehrere Quellen
- Quellenkonflikte werden angezeigt statt still überschrieben
- keine Änderungen an Sonarr
- keine kostenpflichtige IMDb-/AWS-Integration

## Quellen-Priorität

1. `manual_de` – manuell bestätigte deutsche Daten
2. `wikipedia_de` – explizite deutsche/deutschsprachige Erstausstrahlung aus Wikipedia-DE-Tabellen
3. `tvmaze_de` – explizite deutsche TVmaze Country-Premiere-Alternate-Lists
4. `streaming_de` – Deutschland-spezifische Streaming-Verfügbarkeit
5. `tmdb_de` – optionales TMDB Mapping/Fallback
6. `sonarr_tvdb` – letzter Fallback

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

## Entwicklungs-Hinweis

Die aktuellen Parser-/Matcher-Diagnosewerte in der WebUI sind nur für die Entwicklungsphase vorgesehen und werden vor einer öffentlichen Veröffentlichung entfernt.

## Nächste Schritte

1. Abdeckung des neuen Wikipedia-Matchers mit realen Serien prüfen
2. problematische Titel-/Nummerierungsfälle gezielt erweitern
3. Quellenkonflikte und Confidence weiter verfeinern
4. TMDB nur bei Bedarf optional aktivieren
5. später Hybrid-Modus für Freigabe der Sonarr-Suche
6. erst danach optional schreibende Sonarr-Automation
