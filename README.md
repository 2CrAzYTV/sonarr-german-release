# Sonarr German Release

Begleitdienst für Sonarr zur Ermittlung und Anzeige deutscher Veröffentlichungsdaten.

## Aktueller Stand

Version 0.2.4 ist absichtlich **read-only**:

- Verbindung zu Sonarr über API v3
- Serien aus Sonarr einlesen
- kommende Episoden aus Sonarr einlesen
- Sonarr-IMDb-IDs automatisch übernehmen
- TMDb-Mappings optional über externe IDs ergänzen
- SQLite-Datenbank für mehrere Quellen
- WebUI intern auf Port 8788
- Unraid Host-Port 8789
- keine Änderungen an Sonarr
- keine Episode wird automatisch auf monitored/unmonitored gesetzt
- Mehrquellen-Architektur mit Konflikterkennung

## Quellen-Priorität

Das Projekt verlässt sich nicht auf eine einzelne Metadatenquelle.

Priorität:

1. `manual_de` – manuell bestätigte deutsche Daten
2. `imdb_de` – bevorzugte externe Quelle für deutsche Veröffentlichungstermine
3. `streaming_de` – später für Netflix, Disney+, Prime Video usw.
4. `tmdb_de` – Mapping/Fallback bzw. zusätzliche Bestätigung
5. `sonarr_tvdb` – letzter Fallback

Jede Quelle wird separat gespeichert. Bei unterschiedlichen Datumsangaben wird ein Konflikt angezeigt, statt still eine Quelle zu überschreiben.

## IMDb API

Für IMDb wird bewusst **kein Webseiten-Scraping** verwendet. Vorgesehen ist die offizielle IMDb GraphQL API über AWS Data Exchange.

Der Provider ist optional: Ohne IMDb-Zugang startet der Container normal weiter und zeigt den Provider als nicht konfiguriert an.

Optionale Unraid-Container-Variablen für IMDb:

- `IMDB_API_ENDPOINT`
- `IMDB_AWS_REGION` = `us-east-1`
- `IMDB_AWS_ACCESS_KEY_ID`
- `IMDB_AWS_SECRET_ACCESS_KEY`
- `IMDB_AWS_SESSION_TOKEN` – nur falls benötigt

Diese Zugangsdaten gehören ausschließlich in die Unraid-Container-Konfiguration und niemals ins Repository.

## TMDb API

TMDb wird bewusst **nicht als alleinige Quelle für deutsche Episoden-Releasedaten** verwendet.

Wichtig: TMDb bietet für TV-Episoden keinen eigenen Deutschland-Release-Date-Endpunkt wie bei Filmen. Das normale Episodenfeld `air_date` wird deshalb **nicht** als deutsches Veröffentlichungsdatum gespeichert.

TMDb wird aktuell verwendet für:

- Zuordnung IMDb/TVDB → TMDb-Serie
- zusätzliche Serien-/Episoden-Metadaten
- spätere Bestätigung anderer Quellen

Optionale Unraid-Container-Variable:

- `TMDB_API_TOKEN` – TMDb API Read Access Token

Ohne Token läuft der Container normal weiter; der TMDb-Provider bleibt deaktiviert.

## Konfiguration

Für Unraid wird **keine `.env`-Datei verwendet**. Alle Einstellungen werden direkt als Container-Variablen im Unraid-Template gesetzt.

Benötigte Variablen:

- `SONARR_URL`
- `SONARR_API_KEY`
- `COUNTRY` = `DE`
- `LANGUAGE` = `de-DE`
- `TZ` = `Europe/Berlin`
- `DATABASE_PATH` = `/data/releases.sqlite3`
- `READ_ONLY` = `true`
- `PREFERRED_PROVIDER` = `imdb_de`

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

1. TMDb-Token optional in Unraid hinterlegen und Mapping prüfen
2. offiziellen IMDb-GraphQL-Request signieren und testen
3. Episoden einer Sonarr-Serie auf IMDb-Episoden abbilden
4. deutsche Release-Daten pro Episode speichern
5. Streaming-DE-Provider ergänzen
6. Hybrid-Modus für Freigabe der Sonarr-Suche
7. erst danach optional schreibende Sonarr-Automation
