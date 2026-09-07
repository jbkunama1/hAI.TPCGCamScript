# hAI.TPCGCamScript

Sichere, containerisierte Bildverarbeitung für TPCG-Live-Kameras.

## Funktionen

- Verarbeitung von einem oder zwei Kamerabildern
- Auslieferung über SFTP, FTPS und HTTPS
- Kein unverschlisseltes FTP
- Web-Admin mit Live-Vorschau, Logs, Statistiken und Bildstatus
- Browserbasierter Python-Script-Editor für beide Verarbeitungsskripte
- Basic Auth für das Admin-UI
- API-Key-Schutz für die REST-API
- Script-Validierung vor dem Speichern
- Automatische Script-Backups und Audit-Log
- Optionaler Ollama-API-Client
- Veröffentlichung als GHCR-Image per GitHub Actions

## Schnellstart

```bash
mkdir -p /opt/hai-tpcg-cam-script
cd /opt/hai-tpcg-cam-script

curl -fsSL https://raw.githubusercontent.com/jbkunama1/hAI.TPCGCamScript/main/docker-compose.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/jbkunama1/hAI.TPCGCamScript/main/.env.example -o .env

# .env bearbeiten, dann:
docker compose up -d
```

## Konfiguration

Siehe `.env.example` für alle benötigten Umgebungsvariablen.

## Sicherheit

- Verwende SFTP oder FTPS, niemals Plain FTP.
- Setze für Admin, API, SFTP und FTPS jeweils eigene starke Zugangsdaten.
- Sichere FTPS mit einem gültigen Zertifikat; das mitgelieferte selbstsignierte Zertifikat ist nur für Tests.
