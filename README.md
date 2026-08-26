# Sonarr German Release

Begleitdienst für Sonarr zur Ermittlung und Anzeige deutscher Veröffentlichungsdaten.

## Aktueller Stand

Version 0.1.1 ist absichtlich **read-only**:

- Verbindung zu Sonarr über API v3
- Serien aus Sonarr einlesen
- kommende Episoden aus Sonarr einlesen
- SQLite-Datenbank vorbereiten
- WebUI intern auf Port 8788
- Unraid Host-Port 8789
- keine Änderungen an Sonarr
- keine Episode wird automatisch auf monitored/unmonitored gesetzt

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

1. TMDb-Provider für deutsche Daten
2. Zuordnung Sonarr-Serie ↔ TMDb
3. Vergleich Sonarr-Datum ↔ deutsches Datum
4. Quellen-/Vertrauensanzeige
5. Hybrid-Modus
6. erst danach optional schreibende Sonarr-Automation
