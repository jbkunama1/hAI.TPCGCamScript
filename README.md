<div align="center">

# 🎾 hAI.TPCGCamScript

### 📸 Sichere Live-Bildverarbeitung für Tennis- & Padel-Webcams

[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Web%20API-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Gunicorn](https://img.shields.io/badge/Gunicorn-Production-499848?style=for-the-badge&logo=gunicorn&logoColor=white)](https://gunicorn.org/)
[![GitHub Actions](https://img.shields.io/github/actions/workflow/status/jbkunama1/hAI.TPCGCamScript/docker-publish.yml?branch=main&style=for-the-badge&label=GHCR%20Build&logo=githubactions&logoColor=white)](https://github.com/jbkunama1/hAI.TPCGCamScript/actions)
[![Multi-Arch](https://img.shields.io/badge/Arch-amd64%20%2B%20arm64-blueviolet?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/jbkunama1/hAI.TPCGCamScript/pkgs/container/hai.tpcgcamscript)
[![Portainer](https://img.shields.io/badge/Portainer-ready-13BEF9?style=for-the-badge&logo=portainer&logoColor=white)](https://www.portainer.io/)
[![License](https://img.shields.io/github/license/jbkunama1/hAI.TPCGCamScript?style=for-the-badge&color=F59E0B)](LICENSE)

**Containerisierte Verarbeitung, sichere Übertragung und Live-Vorschau für die TPC Grötzingen Tennis- und Padelkameras.**

</div>

---

## ✨ Überblick

`hAI.TPCGCamScript` verarbeitet eingehende Bilder von Tennis- und Padel-Webcams, erzeugt stabile und komprimierte Live-Ausgaben und stellt sie über eine geschützte Verwaltungsoberfläche sowie über HTTP(S), FTP (pure-ftpd) und SFTP bereit.

> [!NOTE]
> **FTP-Stack:** pure-ftpd auf Port 21. Klartext-FTP ist standardmäßig deaktiviert; für Kameras ohne explizites FTPS kann es per `FTP_ALLOW_PLAIN=true` erlaubt werden. TLS ist parallel als Option verfügbar. Der frühere vsftpd/FTPS-Stack (Port 990) wurde entfernt.

## 🏗️ Architektur

```text
Kameras / Uploads
        │
        ├── Tennis: tennis/webcam.jpg
        └── Padel:  padel/YYYY/MM/DD/Padel_00_* / Padel_01_*
        │
        ▼
Python-Worker (Pillow, Intervall PROCESS_INTERVAL_SECONDS)
        │
        ├── Mindestdateigröße prüfen (unvollständige Uploads ignorieren)
        ├── Resize / Crop / Komprimierung
        └── atomare Ausgabe + status.json
        │
        ▼
Stabile Live-Ausgaben in /data/output
        │
        ├── tennis/webcam_live.jpg
        ├── padel/webcam1_live.jpg
        └── padel/webcam2_live.jpg
        │
        ├── 🌐 Flask-Live-Vorschau /live
        ├── 🔐 Admin & API /api/...
        ├── 📁 FTP (pure-ftpd, Port 21)
        └── 🔒 SFTP (Port 22)
```

| Baustein | Technik | Aufgabe |
|---|---|---|
| Web, API & Live-Seite | Flask + Gunicorn auf Container-Port `8080` | Admin, Status, Script-Verwaltung und Bildauslieferung |
| Bildbearbeitung | `app/camera_worker.py` (Python + Pillow) | Resize, Crop, Komprimierung, stabile Ausgabedateien, `status.json` |
| FTP | pure-ftpd / Port `21` | Datei-Upload der Kameras (Unix-Auth, Chroot auf `/data/input`, PASV 30000–30010) |
| SFTP | OpenSSH / Port `22` | Verschlüsselter Dateitransfer (Chroot `/data/input`) |
| Persistenz | Host-Verzeichnisse unter `${DATA_ROOT}` | Input, Output, Skripte, Backups, Logs und Konfiguration |
| Netzwerk | externes Docker-Netz `highfishNetwork` | Anbindung an deine übrigen Stacks |
| Build & Registry | GitHub Actions + GHCR | Multi-Arch-Build (`linux/amd64`, `linux/arm64`) bei Push auf `main` |

## 📷 Kamera-Pipeline

| Ansicht | Quelle | Live-Ausgabe | Beschreibung |
|---|---|---|---|
| 🎾 Tennis / Eingang | `tennis/webcam.jpg` | `tennis/webcam_live.jpg` | Die Webcam überschreibt das Rohbild fortlaufend. Erst eine ausreichend große, vollständig übertragene JPEG (> 80 KB) wird verarbeitet, auf 896×672 skaliert und auf 896×504 zugeschnitten. |
| 🟡 Padel 1 | `padel/YYYY/MM/DD/Padel_00_*.jpg` | `padel/webcam1_live.jpg` | Das zeitlich neueste Bild der Kamera `Padel_00` aus dem Tagesordner (> 20 KB), skaliert auf 896×504. |
| 🟡 Padel 2 | `padel/YYYY/MM/DD/Padel_01_*.jpg` | `padel/webcam2_live.jpg` | Das zeitlich neueste Bild der Kamera `Padel_01` aus dem Tagesordner (> 20 KB), skaliert auf 896×504. |

Der Worker läuft automatisch im Container mit dem Intervall `PROCESS_INTERVAL_SECONDS` (Standard: 30 Sekunden) und schreibt zusätzlich `/data/output/status.json`. Die Routine-Logzeile erscheint nur alle `WORKER_LOG_INTERVAL_SECONDS` (Standard: 300 s); Erfolg und Fehler werden sofort geloggt.

## 🚀 Portainer-Git-Deployment

Die Compose-Datei ist für **Git-basierte Stacks in Portainer** vorbereitet. Sie erwartet ausdrücklich **keine `.env`-Datei im Repository**; alle Werte werden im Bereich **Environment variables** des Portainer-Stacks hinterlegt.

### 1. Datenpfade auf dem Host anlegen

```bash
sudo mkdir -p \
  /opt/hai-tpcg-cam-script/data/input \
  /opt/hai-tpcg-cam-script/data/output \
  /opt/hai-tpcg-cam-script/data/scripts \
  /opt/hai-tpcg-cam-script/data/backups \
  /opt/hai-tpcg-cam-script/data/logs \
  /opt/hai-tpcg-cam-script/data/config
```

### 2. Externes Netzwerk prüfen

```bash
docker network create highfishNetwork   # nur falls noch nicht vorhanden
```

### 3. Stack in Portainer erstellen

1. **Stacks** → **Add stack** → **Repository** auswählen
2. Repository: `https://github.com/jbkunama1/hAI.TPCGCamScript`
3. Compose-Pfad: `docker-compose.yml`
4. Branch/Referenz: `main`
5. Im Bereich **Environment variables** die folgenden Werte setzen
6. **Deploy the stack** wählen

### 4. Pflichtvariablen

> [!CAUTION]
> Die Secret-Werte dürfen nicht als beschreibende Platzhalter gespeichert werden. Verwende für jeden Wert ein eigenes, langes Zufallsgeheimnis.

| Variable | Pflicht | Zweck |
|---|:---:|:---|
| `ADMIN_PASSWORD` | ✅ | Passwort für die Basic-Auth-Verwaltung |
| `API_KEY` | ✅ | Zugriffsschlüssel für die REST-API |
| `SFTP_PASSWORD` | ✅ | Passwort des Transfernutzers (gilt für FTP **und** SFTP) |

### 5. Vollständige Portainer-Variablen

```text
ADMIN_PASSWORD=DEIN_ECHTES_LANGES_ADMIN_PASSWORT
API_KEY=DEIN_ECHTER_LANGER_ZUFAELLIGER_API_KEY
SFTP_PASSWORD=DEIN_ECHTES_TRANSFER_PASSWORT

ADMIN_USER=admin
TZ=Europe/Berlin
SFTP_USER=tpcgtransfer
PUBLIC_BASE_URL=https://cam.example.de
PROCESS_INTERVAL_SECONDS=30
WORKER_LOG_INTERVAL_SECONDS=300

# Externer FTP-Zugriff hinter Fritzbox-Portweiterleitung:
PASV_ADDRESS=DEINE_OEFFENTLICHE_IP_ODER_HOSTNAME
FTP_ALLOW_PLAIN=true
```

## 🔌 Zugänge & Ports

| Dienst | Host-Port | Container-Port | Beispiel |
|---|:---:|:---:|---|
| 🧭 Admin & API | `8067` | `8080` | `http://SERVER-IP:8067/` |
| 📺 Live-Vorschau | `8067` | `8080` | `http://SERVER-IP:8067/live` |
| 📁 FTP | `21` (intern) | `21` | intern `SERVER-IP:21` |
| ↔️ FTP passiv | `30000–30010` | `30000–30010` | Firewall/Router entsprechend freigeben |
| 🔐 SFTP | `2222` | `22` | `sftp -P 2222 tpcgtransfer@SERVER-IP` |

Für den Zugriff über das Internet: Fritzbox-Portweiterleitung extern **521 → intern 21** (Control) sowie **30000–30010 → 30000–30010** (PASV-Datenkanal) auf den Docker-Host. `PASV_ADDRESS` muss die öffentliche IP oder den öffentlichen Hostnamen enthalten.

- `/` ist per **Basic Auth** geschützt (`ADMIN_USER` / `ADMIN_PASSWORD`); der Server sendet `WWW-Authenticate`, sodass Browser automatisch den Login-Dialog anzeigen.
- `/live` und `/output/...` sind ohne Login erreichbar, damit die Live-Bilder öffentlich eingebunden werden können.

### API-Status testen

```bash
curl -H "X-API-Key: DEIN_API_KEY" http://SERVER-IP:8067/api/status
# oder
curl -u "admin:DEIN_ADMIN_PASSWORT" http://SERVER-IP:8067/api/status
```

## 🧩 Funktionen

- ✅ Flask-Dashboard mit Basic Auth inkl. Browser-Login-Dialog (`WWW-Authenticate`)
- ✅ API-Key-Schutz für API-Endpunkte
- ✅ Auslieferung von Live-Bildern unter `/output/...`
- ✅ Automatischer Kamera-Worker (Tennis + Padel) mit Mindestdateigrößen, Tagesordner-Auswahl, Resize/Crop, Komprimierung und `status.json`
- ✅ Produktionsserver über Gunicorn (kein Flask-Dev-Server)
- ✅ Editierbare Python-Verarbeitungsskripte mit Syntaxprüfung, Backups und Audit-Log
- ✅ FTP über pure-ftpd (Unix-Auth, Chroot `/data/input`, PASV-Ports, optionales TLS) + SFTP über OpenSSH
- ✅ Umgebungs-Anzeige im Admin (`/api/info`): alle Variablen sortiert, Secrets maskiert
- ✅ 19 Themes mit dynamischer Erkennung und DB-persistierter Auswahl
- ✅ GitHub Actions Workflow mit Multi-Arch-Build (`linux/amd64`, `linux/arm64`) nach GHCR

## 🗂️ Persistente Verzeichnisse

```text
/data/
├── input/     # eingehende Kamera- bzw. Upload-Bilder
│   ├── tennis/
│   └── padel/YYYY/MM/DD/
├── output/    # komprimierte Live-Bilder und status.json
├── scripts/   # persistent editierbare Python-Skripte (werden aus dem Image befüllt)
├── backups/   # Sicherungen vor Script-Änderungen
├── logs/      # Audit-, Worker-, FTP- und Ausführungsprotokolle
└── config/    # Laufzeitkonfiguration und SQLite-DB (tpcg.db)
```

## 🔐 Sicherheit

- FTP ist standardmäßig TLS-pflichtig (`--tls=2`); Klartext nur explizit per `FTP_ALLOW_PLAIN=true` freischaltbar.
- Nutze für Admin, API und Dateitransfer unterschiedliche, starke Passwörter/Keys.
- Veröffentliche den Admin-Port nicht ungeschützt im Internet; bevorzugt VPN, IP-Allowlist oder Cloudflare Access.
- Das im Image erzeugte TLS-Zertifikat ist selbstsigniert und nur für Tests gedacht.
- Editierbare Python-Skripte sind eine administrative Hochrisikofunktion – den Admin-Zugang besonders schützen.

## 🛠️ Betrieb & Fehlerdiagnose

| Symptom | Ursache / Lösung |
|---|---|
| FTP: `connection refused` intern | Prüfen, ob der FTP-Server läuft: `docker exec hai-tpcg-cam-script ss -tln \| grep :21` und `docker exec hai-tpcg-cam-script cat /data/logs/ftpd-start.log`. |
| FTP: Login schlägt mit 530 fehl | Benutzername = Wert von `SFTP_USER` (z. B. `tpcgtransfer`), Passwort = `SFTP_PASSWORD`. Die Shell `/usr/sbin/nologin` ist im Image in `/etc/shells` freigegeben. |
| FTP: Verbindung klappt, aber keine Dateiliste/-Upload | PASV-Datenkanal fehlt: Router-Weiterleitung `30000–30010` auf den Host einrichten und `PASV_ADDRESS` auf die öffentliche IP/den Hostnamen setzen. |
| `env file .../.env not found` | Behoben: Die Compose-Datei verwendet kein `env_file`; Variablen kommen aus Portainer. Stack neu deployen. |
| `no matching manifest for linux/arm64/v8` | Das GHCR-Image wird Multi-Arch gebaut; nach einem erfolgreichen Actions-Lauf in Portainer **Pull latest image**. |
| Kein neues Live-Bild | Prüfen, ob Rohbilder in `/data/input/tennis` bzw. `/data/input/padel/YYYY/MM/DD` ankommen und die Mindestgrößen (80 KB Tennis, 20 KB Padel) erreichen; Worker-Log unter `/data/logs/worker.log` prüfen. |

---

<div align="center">

🎾 **TPC Grötzingen** · gebaut mit 🐍 Python, 🐳 Docker und ❤️

</div>
