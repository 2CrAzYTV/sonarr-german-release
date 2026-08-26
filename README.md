# Sonarr German Release

Begleitdienst für Sonarr zur Ermittlung und Anzeige deutscher Veröffentlichungs- und Streaming-Informationen.

## Aktueller Stand

Version 0.3.0 ist absichtlich **read-only**:

- Verbindung zu Sonarr über API v3
- Serien aus Sonarr einlesen
- kommende Episoden aus Sonarr einlesen
- TVmaze-Mapping über vorhandene IMDb-/TVDB-IDs
- echte deutsche Country-Premiere-Daten aus TVmaze Alternate Lists
- TMDB-Mappings über vorhandene externe IDs
- DE-Streaming-Verfügbarkeit über TMDB Watch Providers / JustWatch
- SQLite-Datenbank für mehrere Quellen
- WebUI intern auf Port 8788
- Unraid Host-Port 8789
- keine Änderungen an Sonarr
- keine Episode wird automatisch auf monitored/unmonitored gesetzt
- Mehrquellen-Architektur mit Konflikterkennung
- keine kostenpflichtige IMDb-/AWS-Integration

## Quellen-Priorität

Das Projekt verlässt sich nicht auf eine einzelne Metadatenquelle.

Priorität:

1. `manual_de` – manuell bestätigte deutsche Daten
2. `tvmaze_de` – explizite deutsche Country-Premiere-Alternate-Lists
3. `streaming_de` – Deutschland-spezifische Streaming-Verfügbarkeit
4. `tmdb_de` – TMDB Mapping/Fallback bzw. zusätzliche Bestätigung
5. `sonarr_tvdb` – letzter Fallback

Jede Quelle wird separat behandelt. Bei unterschiedlichen Datumsangaben wird ein Konflikt angezeigt, statt still eine Quelle zu überschreiben.

## TVmaze

TVmaze wird über die kostenlose öffentliche REST-API verwendet. Es ist kein API-Key erforderlich.

Die Anwendung nutzt TVmaze nur dann als deutsches Release-Datum, wenn TVmaze für die Serie eine Alternate List mit dem Land `DE` bereitstellt. Normale TVmaze-Episodendaten bzw. Weltpremieren werden nicht automatisch als deutsches Datum interpretiert.

Verwendete Funktionen:

- exaktes Serien-Mapping über vorhandene IMDb- oder TVDB-ID
- Country-Premiere Alternate Lists für Deutschland
- Zuordnung der Alternate Episodes zur ursprünglichen Staffel-/Episodennummer
- Confidence `high`, wenn TVmaze eine Uhrzeit liefert
- Confidence `medium`, wenn nur das Datum bekannt ist

Es sind keine zusätzlichen Unraid-Variablen erforderlich.

## TMDB API

TMDB wird bewusst **nicht als alleinige Quelle für deutsche Episoden-Releasedaten** verwendet.

Wichtig: TMDB bietet für TV-Episoden keinen eigenen Deutschland-Release-Date-Endpunkt wie bei Filmen. Das normale Episodenfeld `air_date` wird deshalb **nicht** als deutsches Veröffentlichungsdatum gespeichert.

TMDB wird aktuell verwendet für:

- Zuordnung vorhandener externer Serien-IDs zu einer TMDB-Serie
- zusätzliche Serien-/Episoden-Metadaten
- DE-Streaming-Verfügbarkeit über Watch Providers / JustWatch
- spätere Bestätigung anderer kostenloser Quellen

Unraid-Container-Variable:

- `TMDB_API_TOKEN` – TMDB API Read Access Token

Ohne Token läuft der Container normal weiter; der TMDB-Provider bleibt deaktiviert.

### Kosten

Die TMDB Developer API ist für **nicht-kommerzielle Nutzung kostenlos**, sofern TMDB korrekt als Quelle genannt wird. Für kommerzielle Nutzung ist eine separate Vereinbarung mit TMDB erforderlich.

### Attribution und Branding

Die WebUI enthält einen eigenen Bereich **Credits & Datenquellen** mit:

- TVmaze-Nennung und Link
- einem von TMDB freigegebenen Logo
- einem Link zu `https://www.themoviedb.org`
- dem vorgeschriebenen Hinweis: `This product uses the TMDB API but is not endorsed or certified by TMDB.`
- einer separaten JustWatch-Attribution für Watch-Provider-Daten

Das TMDB-Logo wird kleiner als die Kennzeichnung der Anwendung dargestellt und weder farblich noch im Seitenverhältnis verändert.

### Cache-Aufbewahrung

TMDB-Inhalte dürfen laut API Terms of Use nicht länger als sechs Monate gecacht werden. Persistierte TMDB-Serienzuordnungen werden deshalb spätestens nach **180 Tagen** erneut geprüft. Streaming-Verfügbarkeiten werden nur im Arbeitsspeicher gecacht und bei einem Container-Neustart verworfen.

## Konfiguration

Für Unraid wird **keine `.env`-Datei verwendet**. Alle Einstellungen werden direkt als Container-Variablen im Unraid-Template gesetzt.

Benötigte Basisvariablen:

- `SONARR_URL`
- `SONARR_API_KEY`
- `COUNTRY` = `DE`
- `LANGUAGE` = `de-DE`
- `TZ` = `Europe/Berlin`
- `DATABASE_PATH` = `/data/releases.sqlite3`
- `READ_ONLY` = `true`
- `PREFERRED_PROVIDER` = `tvmaze_de`
- `TMDB_API_TOKEN`

Secrets und Zugangsdaten werden niemals im Repository hinterlegt.

## Unraid

Vorgesehene Werte:

- Container Name: `sonarr-german-release`
- Repository: `ghcr.io/2crazytv/sonarr-german-release:latest`
- WebUI Host-Port: `8789`
- Container-Port: `8788`
- Appdata: `/mnt/cache/appdata/sonarr-german-release/data`
- Container-Pfad: `/data`
- Restart Policy: `unless-stopped`

## Sonarr API-Key

Sonarr → Settings → General → Security → API Key

## Nächste Schritte

1. TVmaze-DE-Abdeckung mit realen Serien aus der Bibliothek prüfen
2. Quellenkonflikte und Confidence weiter verfeinern
3. zusätzliche kostenlose DE-Quellen evaluieren
4. Hybrid-Modus für Freigabe der Sonarr-Suche
5. erst danach optional schreibende Sonarr-Automation
