# Sonarr German Release

Begleitdienst für Sonarr zur Ermittlung und Anzeige deutscher Veröffentlichungsdaten.

## Aktueller Stand

Version 0.2 ist absichtlich **read-only**:

- Verbindung zu Sonarr über API v3
- Serien aus Sonarr einlesen
- kommende Episoden aus Sonarr einlesen
- SQLite-Datenbank vorbereiten
- WebUI intern auf Port 8788
- Unraid Host-Port 8789
- keine Änderungen an Sonarr
- keine Episode wird automatisch auf monitored/unmonitored gesetzt
- Mehrquellen-Architektur für deutsche Releasedaten

## Quellen-Priorität

Das Projekt verlässt sich nicht auf eine einzelne Metadatenquelle.

Priorität:

1. `IMDb DE` – bevorzugte Quelle für deutsche Veröffentlichungstermine
2. `Streaming DE` – später für Netflix, Disney+, Prime Video usw.
3. `TMDb DE` – nur Fallback bzw. zusätzliche Bestätigung
4. `Sonarr/TVDB` – letzter Fallback

Jede Quelle wird separat gespeichert. Bei unterschiedlichen Datumsangaben wird ein Konflikt angezeigt, statt still eine Quelle zu überschreiben.

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
- WebUI Host-Port: `8789`
- Container-Port: `8788`
- Appdata: `/mnt/user/appdata/sonarr-german-release/`
- Container-Pfad: `/data`
- Restart Policy: `unless-stopped`

## Sonarr API-Key

Sonarr → Settings → General → Security → API Key

## Nächste Schritte

1. robuste IMDb-DE-Abfrage implementieren
2. Serien-/Episoden-Zuordnung über IMDb/TVDB/TMDb-IDs
3. Quellenkonflikte in der WebUI anzeigen
4. optional Streaming-DE-Provider ergänzen
5. Hybrid-Modus für Freigabe der Sonarr-Suche
6. erst danach optional schreibende Sonarr-Automation
