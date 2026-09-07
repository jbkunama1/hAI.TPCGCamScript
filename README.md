<div align="center">

# 🎾 hAI.TPCGCamScript

### 📸 Sichere Live-Bildverarbeitung für Tennis- & Padel-Webcams

[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Web%20API-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![GitHub Actions](https://img.shields.io/github/actions/workflow/status/jbkunama1/hAI.TPCGCamScript/docker-publish.yml?branch=main&style=for-the-badge&label=GHCR%20Build&logo=githubactions&logoColor=white)](https://github.com/jbkunama1/hAI.TPCGCamScript/actions)
[![Portainer](https://img.shields.io/badge/Portainer-ready-13BEF9?style=for-the-badge&logo=portainer&logoColor=white)](https://www.portainer.io/)
[![License](https://img.shields.io/github/license/jbkunama1/hAI.TPCGCamScript?style=for-the-badge&color=F59E0B)](LICENSE)

**Containerisierte Verarbeitung, sichere Übertragung und Live-Vorschau für die TPC Grün-Gold Grötzingen Tennis- und Padelkameras.**

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
Python-Bildverarbeitung (Pillow)
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
| Web, API & Live-Seite | Flask auf Port `8080` | Admin, Status, Script-Verwaltung und Bildauslieferung |
| Bildbearbeitung | Python + Pillow | Resize, Crop, Komprimierung und stabile Ausgabedateien |
| SFTP | OpenSSH / Port `22` | Verschlüsselter Dateitransfer |
| FTPS | vsftpd / Port `990` | TLS-geschützter Dateitransfer mit passiven Ports |
| Persistenz | Host-Verzeichnisse | Input, Output, Skripte, Backups, Logs und Konfiguration |
| Build & Registry | GitHub Actions + GHCR | Automatischer Docker-Image-Build bei Push auf `main` |

## 📷 Kamera-Pipeline

| Ansicht | Quelle | Live-Ausgabe | Beschreibung |
|---|---|---|---|
| 🎾 Tennis / Eingang | `tennis/webcam.jpg` | `tennis/webcam_live.jpg` | Die Webcam überschreibt das Rohbild fortlaufend. Erst ein ausreichend großes, vollständig übertragenes JPEG wird verarbeitet. |
| 🟡 Padel 1 | `padel/YYYY/MM/DD/Padel_00_*.jpg` | `padel/webcam1_live.jpg` | Das zeitlich neueste Bild der Kamera `Padel_00` wird aus dem Tagesordner ausgewählt. |
| 🟡 Padel 2 | `padel/YYYY/MM/DD/Padel_01_*.jpg` | `padel/webcam2_live.jpg` | Das zeitlich neueste Bild der Kamera `Padel_01` wird aus dem Tagesordner ausgewählt. |

Die Live-Seite verwendet ausschließlich die stabilen Ausgabedateien:

```text
/output/tennis/webcam_live.jpg
/output/padel/webcam1_live.jpg
/output/padel/webcam2_live.jpg
```

Ein Zeitstempel-Parameter verhindert, dass Browser alte Kameraaufnahmen aus dem Cache anzeigen.

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

### 2. Stack in Portainer erstellen

1. **Stacks** → **Add stack** → **Repository** auswählen
2. Repository: `https://github.com/jbkunama1/hAI.TPCGCamScript`
3. Compose-Pfad: `docker-compose.yml`
4. Branch/Referenz: `main`
5. Im Bereich **Environment variables** die folgenden Werte setzen
6. **Deploy the stack** wählen

### 3. Pflichtvariablen

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

### 4. Vollständige Portainer-Variablen

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
| 🧭 Admin & API | `8088` | `8080` | `http://SERVER-IP:8088/` |
| 📺 Live-Vorschau | `8088` | `8080` | `http://SERVER-IP:8088/live` |
| 🔐 SFTP | `2222` | `22` | `sftp -P 2222 tpcgtransfer@SERVER-IP` |
| 🔒 FTPS | `9900` | `990` | `ftps://SERVER-IP:9900` |
| ↔️ FTPS passiv | `30000–30010` | `30000–30010` | Firewall/NAT entsprechend freigeben |

### API-Status testen

```bash
curl \
  -H "X-API-Key: DEIN_API_KEY" \
  http://SERVER-IP:8088/api/status
```

## 🧩 Funktionen

- ✅ Flask-Dashboard mit Basic Auth
- ✅ API-Key-Schutz für API-Endpunkte
- ✅ Auslieferung von Live-Bildern unter `/output/...`
- ✅ Editierbare Python-Verarbeitungsskripte
- ✅ Syntaxprüfung vor dem Speichern
- ✅ Versionierte Script-Backups in `/data/backups`
- ✅ JSONL-Audit-Log in `/data/logs/audit.jsonl`
- ✅ Ausführen von Verarbeitungsskripten mit 30-Sekunden-Timeout
- ✅ SFTP und FTPS, kein Klartext-FTP
- ✅ GitHub Actions Workflow für GHCR
- 🟡 Original-TPCG-Theme und Theme-Wechsel im Admin-Bereich: geplant
- 🟡 Automatischer Bild-Worker / Scheduler: geplant
- 🟡 Gültiges externes TLS-Zertifikat für FTPS: für Produktion empfohlen

## 🗂️ Persistente Verzeichnisse

```text
/data/
├── input/     # eingehende Kamera- bzw. Upload-Bilder
├── output/    # komprimierte Live-Bilder und status.json
├── scripts/   # persistent editierbare Python-Skripte
├── backups/   # Sicherungen vor Script-Änderungen
├── logs/      # Audit- und Ausführungsprotokolle
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
| `env file .../.env not found` | Aktuellen `main`-Stand abrufen und den Stack erneut deployen. Die Compose-Datei verwendet kein `env_file` mehr. |
| `manifest unknown` oder `pull access denied` | GHCR-Workflow in GitHub Actions prüfen; das Image muss gebaut und für den Server zugreifbar sein. |
| Kein neues Live-Bild | Prüfen, ob Rohbilder in `/data/input` ankommen und das passende Verarbeitungsskript ausgeführt wird. |
| FTPS kann verbinden, zeigt aber keine Liste | Passive Ports `30000–30010` in Firewall, Router und Docker freigeben. |
| SFTP/FTPS-Anmeldung schlägt fehl | Aktuell wird der Transfernutzer aus `SFTP_USER` / `SFTP_PASSWORD` angelegt; für erste Tests diese Werte verwenden. |

## 🗺️ Roadmap

- [ ] Originales TPCG-Webcam-Design einschließlich Logo und Platzhaltergrafiken als Standard-Theme integrieren
- [ ] Modernes Kartenlayout als Theme 2 beibehalten
- [ ] Geschützte Theme-Auswahl unter `/admin/themes` und `/api/theme`
- [ ] PHP-Bildlogik vollständig als Python-Worker abbilden: Mindestdateigrößen, Tagesordner, Zeitstempel-Auswahl, Crop und Komprimierung
- [ ] Scheduler/Watcher für automatische Verarbeitung nach `PROCESS_INTERVAL_SECONDS`
- [ ] Strukturierte Logs und Gesundheitsprüfung
- [ ] Produktionstaugliche TLS- und Chroot-Härtung

---

<div align="center">

🎾 **TPC Grün-Gold Grötzingen** · gebaut mit 🐍 Python, 🐳 Docker und ❤️

</div>
