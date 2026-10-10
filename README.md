# hAI.TPCGCamScript

Der Stack besteht aus einem einzigen Container, der alle Dienste bereitstellt:

- **Flask‑App** (Gunicorn) – Admin‑UI, API und Live‑Vorschau (Port 8080)
- **sshd** – SFTP‑Zugang (Port 22, nur verschlüsselt)
- **vsftpd** – explizites FTPS (Port 990 + passive‑Ports 30000‑30010)

> **Hinweis:** Es wird **kein** unverschlüsseltes FTP (Port 21) mehr angeboten.

## Docker‑Compose (einzelner Service)
```yaml
services:
  hai-tpcg-cam-script:
    build: .
    container_name: hai-tpcg-cam-script
    restart: unless-stopped
    ports:
      - "8088:8080"   # Flask UI
      - "2222:22"     # SFTP/SSH
      - "9900:990"    # FTPS
      - "30000-30010:30000-30010"  # FTPS passive‑Ports
    env_file:
      - .env
    volumes:
      - ./data/input:/data/input
      - ./data/output:/data/output
      - ./data/scripts:/data/scripts
      - ./data/backups:/data/backups
      - ./data/logs:/data/logs
      - ./data/config:/data/config
```

## Log‑Rotation
Die Anwendung verwendet jetzt `RotatingFileHandler` für die Log‑Dateien `app.log` und `worker.log`. Pro Log‑Datei werden maximal **5 MiB** gespeichert, wobei **3** Backups behalten werden. Ältere Einträge werden automatisch verworfen, sodass das Log‑Verzeichnis nicht unendlich wächst.

## Schnell‑Start
1. **Umgebungsvariablen** in `.env.example` anpassen (Passwörter, API‑Key, etc.).
2. `docker compose up -d` starten – alle Komponenten laufen im selben Container.
3. Admin‑UI unter `http://localhost:8088` öffnen (Basic‑Auth mit `ADMIN_USER`/`ADMIN_PASSWORD`).
4. SFTP‑Zugang über Port 2222 (`tpcgtransfer`/`SFTP_PASSWORD`).
5. FTPS‑Zugang über Port 9900 (`tpcgtransfer`/`FTPS_PASSWORD`).

## Verzeichnisstruktur (im Container)
```
/data
├─ input/      # Eingehende Bilder von Kameras
├─ output/     # Verarbeitete Bilder + status.json
├─ scripts/    # Python‑Skripte (process_single.py, process_pair.py)
├─ backups/    # Script‑Backups bei jedem Speichern
├─ logs/       # app.log, worker.log (rotierend)
└─ config/     # SQLite‑DB und weitere Konfigurationen
```

## Weiterführende Dokumentation
- **API‑Referenz**: `GET /api/*` Endpunkte (Status, Themes, Paths, Links, Cameras, Users).
- **Skript‑Editor**: `GET /api/scripts` und `POST /api/scripts/<name>` zum Bearbeiten und Ausführen.
- **Audit‑Log**: `GET /api/audit` liefert Aktionen mit Zeitstempel.

## Lizenz
MIT – siehe `LICENSE`.

