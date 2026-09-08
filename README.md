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

`hAI.TPCGCamScript` verarbeitet eingehende Bilder von Tennis- und Padel-Webcams, erzeugt stabile und komprimierte Live-Ausgaben und stellt sie über eine geschützte Verwaltungsoberfläche sowie über HTTP(S), SFTP und FTPS bereit.

> [!IMPORTANT]
> **Kein Klartext-FTP:** Port 21 wird nicht veröffentlicht. Für Dateiübertragungen stehen ausschließlich SFTP und TLS-geschütztes FTPS zur Verfügung.

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
        ├── 🔒 SFTP
        └── 🔒 FTPS
```

| Baustein | Technik | Aufgabe |
|---|---|---|
| Web, API & Live-Seite | Flask + Gunicorn auf Container-Port `8080` | Admin, Status, Script-Verwaltung und Bildauslieferung |
| Bildbearbeitung | `app/camera_worker.py` (Python + Pillow) | Resize, Crop, Komprimierung, stabile Ausgabedateien, `status.json` |
| SFTP | OpenSSH / Port `22` | Verschlüsselter Dateitransfer (Chroot `/data/sftp`) |
| FTPS | vsftpd / Port `990` | TLS-geschützter Dateitransfer mit passiven Ports |
| Persistenz | Host-Verzeichnisse unter `${DATA_ROOT}` | Input, Output, Skripte, Backups, Logs und Konfiguration |
| Netzwerk | externes Docker-Netz `highfishNetwork` | Anbindung an deine übrigen Stacks |
| Build & Registry | GitHub Actions + GHCR | Multi-Arch-Build (`linux/amd64`, `linux/arm64`) bei Push auf `main` |

## 📷 Kamera-Pipeline

| Ansicht | Quelle | Live-Ausgabe | Beschreibung |
|---|---|---|---|
| 🎾 Tennis / Eingang | `tennis/webcam.jpg` | `tennis/webcam_live.jpg` | Die Webcam überschreibt das Rohbild fortlaufend. Erst eine ausreichend große, vollständig übertragene JPEG (> 80 KB) wird verarbeitet, auf 896×672 skaliert und auf 896×504 zugeschnitten. |
| 🟡 Padel 1 | `padel/YYYY/MM/DD/Padel_00_*.jpg` | `padel/webcam1_live.jpg` | Das zeitlich neueste Bild der Kamera `Padel_00` aus dem Tagesordner (> 20 KB), skaliert auf 896×504. |
| 🟡 Padel 2 | `padel/YYYY/MM/DD/Padel_01_*.jpg` | `padel/webcam2_live.jpg` | Das zeitlich neueste Bild der Kamera `Padel_01` aus dem Tagesordner (> 20 KB), skaliert auf 896×504. |

Die Live-Seite verwendet ausschließlich die stabilen Ausgabedateien:

```text
/output/tennis/webcam_live.jpg
/output/padel/webcam1_live.jpg
/output/padel/webcam2_live.jpg
```

Der Worker läuft automatisch im Container mit dem Intervall `PROCESS_INTERVAL_SECONDS` (Standard: 30 Sekunden) und schreibt zusätzlich `/data/output/status.json`.

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

Der Stack erwartet das externe Netzwerk `highfishNetwork`:

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
> Die vier Secret-Werte dürfen nicht als beschreibende Platzhalter gespeichert werden. Verwende für jeden Wert ein eigenes, langes Zufallsgeheimnis.

| Variable | Pflicht | Zweck |
|---|:---:|---|
| `ADMIN_PASSWORD` | ✅ | Passwort für die Basic-Auth-Verwaltung |
| `API_KEY` | ✅ | Zugriffsschlüssel für die REST-API |
| `SFTP_PASSWORD` | ✅ | Passwort des Transfernutzers |
| `FTPS_PASSWORD` | ✅ | Für spätere getrennte FTPS-Nutzerverwaltung vorgesehen |

Starke Werte erzeugen:

```bash
openssl rand -base64 32  # ADMIN_PASSWORD
openssl rand -base64 32  # API_KEY
openssl rand -base64 24  # SFTP_PASSWORD
openssl rand -base64 24  # FTPS_PASSWORD
```

### 5. Vollständige Portainer-Variablen

```text
ADMIN_PASSWORD=DEIN_ECHTES_LANGES_ADMIN_PASSWORT
API_KEY=DEIN_ECHTER_LANGER_ZUFAELLIGER_API_KEY
SFTP_PASSWORD=DEIN_ECHTES_SFTP_PASSWORT
FTPS_PASSWORD=DEIN_ECHTES_FTPS_PASSWORT

ADMIN_USER=admin
TZ=Europe/Berlin
SFTP_USER=tpcgtransfer
FTPS_USER=tpcgtransfer
DATA_ROOT=/opt/hai-tpcg-cam-script/data
PUBLIC_BASE_URL=https://cam.example.de
PROCESS_INTERVAL_SECONDS=30
OLLAMA_ENABLED=false
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llava
```

## 🔌 Zugänge & Ports

| Dienst | Host-Port | Container-Port | Beispiel |
|---|:---:|:---:|---|
| 🧭 Admin & API | `8067` | `8080` | `http://SERVER-IP:8067/` |
| 📺 Live-Vorschau | `8067` | `8080` | `http://SERVER-IP:8067/live` |
| 🔐 SFTP | `2222` | `22` | `sftp -P 2222 tpcgtransfer@SERVER-IP` |
| 🔒 FTPS | `9900` | `990` | `ftps://SERVER-IP:9900` |
| ↔️ FTPS passiv | `30000–30010` | `30000–30010` | Firewall/NAT entsprechend freigeben |

- `/` ist per **Basic Auth** geschützt (`ADMIN_USER` / `ADMIN_PASSWORD`); der Server sendet `WWW-Authenticate`, sodass Browser automatisch den Login-Dialog anzeigen.
- `/live` und `/output/...` sind ohne Login erreichbar, damit die Live-Bilder öffentlich eingebunden werden können.

### API-Status testen

```bash
curl \
  -H "X-API-Key: DEIN_API_KEY" \
  http://SERVER-IP:8067/api/status
```

oder mit Basic Auth:

```bash
curl -u "admin:DEIN_ADMIN_PASSWORT" http://SERVER-IP:8067/api/status
```

## 🧩 Funktionen

- ✅ Flask-Dashboard mit Basic Auth inkl. Browser-Login-Dialog (`WWW-Authenticate`)
- ✅ API-Key-Schutz für API-Endpunkte
- ✅ Auslieferung von Live-Bildern unter `/output/...`
- ✅ Automatischer Kamera-Worker (Tennis + Padel) mit Mindestdateigrößen, Tagesordner-Auswahl, Resize/Crop, Komprimierung und `status.json`
- ✅ Produktionsserver über Gunicorn (kein Flask-Dev-Server)
- ✅ Editierbare Python-Verarbeitungsskripte mit Syntaxprüfung, Backups und Audit-Log
- ✅ SFTP mit sauberem Chroot (`/data/sftp`) und FTPS, kein Klartext-FTP
- ✅ GitHub Actions Workflow mit Multi-Arch-Build (`linux/amd64`, `linux/arm64`) nach GHCR
- ✅ Anbindung an externes Netzwerk `highfishNetwork`
- 🟡 Theme-Dateien `web/themes/original` und `web/themes/modern` sowie Theme-Admin-HTML vorhanden; API-Verdrahtung (`/api/theme`, `/admin/themes`, `theme.json`) folgt
- 🟡 TPCG-Bildassets (Logos, Platzhalter) müssen noch als Dateien ins Repository
- 🟡 Gültiges externes TLS-Zertifikat für FTPS: für Produktion empfohlen

## 🗂️ Persistente Verzeichnisse

```text
/data/
├── input/     # eingehende Kamera- bzw. Upload-Bilder
│   ├── tennis/
│   └── padel/YYYY/MM/DD/
├── output/    # komprimierte Live-Bilder und status.json
├── scripts/   # persistent editierbare Python-Skripte
├── backups/   # Sicherungen vor Script-Änderungen
├── logs/      # Audit-, Worker- und Ausführungsprotokolle
└── config/    # Laufzeitkonfiguration, z.B. Themes
```

## 🔐 Sicherheit

- Verwende nur **SFTP** oder **FTPS**; Klartext-FTP ist absichtlich nicht verfügbar.
- Nutze für Admin, API und Dateitransfer unterschiedliche, starke Passwörter/Keys.
- Veröffentliche den Admin-Port nicht ungeschützt im Internet.
- Nutze für den Admin-Zugang bevorzugt VPN, IP-Allowlist oder Cloudflare Access.
- Das im Image erzeugte FTPS-Zertifikat ist selbstsigniert und nur für Tests gedacht. Binde für produktive Nutzung ein gültiges Zertifikat als Secret oder Volume ein.
- Editierbare Python-Skripte sind eine administrative Hochrisikofunktion. Der Admin-Zugang muss deshalb besonders geschützt sein.

## 🛠️ Betrieb & Fehlerdiagnose

| Symptom | Ursache / Lösung |
|---|---|
| `env file .../.env not found` | Behoben: Die Compose-Datei verwendet kein `env_file` mehr; Variablen kommen aus Portainer. Stack neu deployen. |
| `no matching manifest for linux/arm64/v8` | Das GHCR-Image war noch nicht Multi-Arch. Der Workflow baut jetzt `linux/amd64,linux/arm64`; nach einem erfolgreichen Actions-Lauf in Portainer **Pull latest image** und ggf. das lokale alte Image löschen. |
| `/venv/bin/gunicorn: No such file or directory` | Behoben: `gunicorn` steht in `requirements.txt`; Image neu bauen und ziehen. |
| `chown: invalid user 'tpcgtransfer:tpcgtransfer'` | Behoben: Der SFTP-Nutzer wird im Entrypoint jetzt vor dem `chown` angelegt. |
| `{"error":"Unauthorized"}` bei `http://SERVER-IP:8067/` | Erwartet: Basic Auth ist aktiv. Browser zeigt nach dem Fix den Login-Dialog; alternativ `curl -u admin:PASS` oder `X-API-Key` verwenden. `/live` bleibt öffentlich. |
| Kein neues Live-Bild | Prüfen, ob Rohbilder in `/data/input/tennis` bzw. `/data/input/padel/YYYY/MM/DD` ankommen und die Mindestgrößen (80 KB Tennis, 20 KB Padel) erreichen; Worker-Log unter `/data/logs/worker-errors.log` prüfen. |
| FTPS kann verbinden, zeigt aber keine Liste | Passive Ports `30000–30010` in Firewall, Router und Docker freigeben. |
| SFTP/FTPS-Anmeldung schlägt fehl | Aktuell wird der Transfernutzer aus `SFTP_USER` / `SFTP_PASSWORD` angelegt; für erste Tests diese Werte verwenden. |

## 🗺️ Roadmap

- [x] PHP-Bildlogik als Python-Worker abbilden (Mindestdateigrößen, Tagesordner, Zeitstempel-Auswahl, Crop, Komprimierung)
- [x] Scheduler für automatische Verarbeitung nach `PROCESS_INTERVAL_SECONDS`
- [x] Gunicorn statt Flask-Entwicklungsserver
- [x] Multi-Arch-GHCR-Image (amd64 + arm64)
- [x] `highfishNetwork`-Anbindung
- [x] HTTP-Port nach außen auf `8067`
- [ ] Theme-API (`GET/POST /api/theme`), Admin-Route `/admin/themes` und Persistenz in `/data/config/theme.json` verdrahten
- [ ] Originales TPCG-Webcam-Design einschließlich Logo- und Platzhaltergrafiken als Standard-Theme ausliefern
- [ ] Strukturierte Logs und Gesundheitsprüfung
- [ ] Produktionstaugliche TLS-Härtung für FTPS

---

<div align="center">

🎾 **TPC Grötzingen** · gebaut mit 🐍 Python, 🐳 Docker und ❤️

</div>
