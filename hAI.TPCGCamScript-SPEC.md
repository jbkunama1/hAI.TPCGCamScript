# hAI.TPCGCamScript – Voll specification

## Projekt-Ü°bersicht

**Repository:**  
https://github.com/jbkunama1/hAI.TPCGCamScript

**Ziel:**  
Containerisierte Bildverarbeitung fä°¼r TPCG-Live-Kameras mit:

- Verarbeitung von einem oder zwei Kamerabildern (Zuschneiden)
- Auslieferung ä%ber SFTP, FTPS und HTTPS
- **Kein unverschlä°¼sseltes FTP**
- Web-Admin mit:
  - Live-Vorschau
  - Logs
  - Statistiken
  - Bildstatus
- Browserbasierter Python-Script-Editor fä°¼r beide Verarbeitungsskripte
- Basic Auth fä°¼r das Admin-UI
- API-Key-Schutz fä°¼r die REST-API
- Script-Validierung vor dem Speichern
- Automatische Script-Backups und Audit-Log
- Optionaler Ollama-API-Client
- Verä¶¼ffentlichung als GHCR-Image per GitHub Actions

---

## Architektur

### Container-Komponenten

- **Basis:** Debian bookworm-slim
- **Dienste im Container:**
  - `sshd` (SFTP ä%ber Port 22)
  - `vsftpd` (FTPS explizit, Port 990 + passive Ports)
  - Flask-Webserver (Admin + API + Live-Vorschau, Port 8080)
- **Verarbeitung:**
  - Python-Skripte:
    - `process_single.py` – Ein Bild zuschneiden
    - `process_pair.py` – Zwei Bilder zuschneiden / kombinieren
- **Speicher:**
  - `/data/input` – Eingehende Bilder (von Kameras oder Upload)
  - `/data/output` – Zuschnitt-Ergebnisse + status.json
  - `/data/scripts` – Persistente Skripte (werden in Container kopiert)
  - `/data/backups` – Script-Backups bei jedem Speichern
  - `/data/logs` – Anwendungs- und Audit-Logs
  - `/data/config` – Konfigs (optional)

### Netzwerk-Ports

| Port | Dienst | Beschreibung |
|------|--------|--------------|
| 8080 | Flask  | Admin-UI, API, Live-Vorschau |
| 22   | SSHD   | SFTP-Zugang (nur verschlä°¼sselt) |
| 990  | vsftpd | Explizites FTPS (TLS) |
| 30000–30010 | vsftpd | FTPS Passive-Ports |

**Wichtig:**  
Es wird **kein** unverschlä°¼sseltes FTP-Port 21 exponiert.

---

## Verzeichnisstruktur

```text
hAI.TPCGCamScript/
├─ .github/
│  └─ workflows/
│     └─ docker-publish.yml
├─ app/
│  ├─ main.py
│  ├─ scripts_api.py
│  ├─ auth.py
│  └─ utils.py
├─ config/
│  ├─ vsftpd.conf
│  ├─ sshd_config
│  └─ ssl/
│     ├─ server.crt
│     └─ server.key
├─ scripts/
│  ├─ entrypoint.sh
│  └─ init_users.sh
├─ web/
│  └─ live/
│     └─ tpcg-live.html
├─ data/
│  ├─ input/
│  ├─ output/
│  ├─ scripts/
│  ├─ backups/
│  ├─ logs/
│  └─ config/
├─ docker-compose.yml
├─ Dockerfile
├─ requirements.txt
├─ .env.example
└─ README.md
```

---

## Dockerfile

```dockerfile
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    openssh-server vsftpd \
    libjpeg-dev zlib1g-dev \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# SSH
RUN mkdir -p /run/sshd
RUN ssh-keygen -A

# FTPS SSL
RUN mkdir -p /etc/vsftpd/ssl
RUN openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout /etc/vsftpd/ssl/server.key \
    -out /etc/vsftpd/ssl/server.crt \
    -subj "/CN=tpcg-cam-script"

COPY config/vsftpd.conf /etc/vsftpd/vsftpd.conf
COPY config/sshd_config /etc/ssh/sshd_config

WORKDIR /app
COPY requirements.txt .
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY scripts/ ./scripts/
COPY web/ ./web/
RUN chmod +x scripts/*.sh

EXPOSE 22 990 8080

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
```

---

## requirements.txt

```text
flask==3.1.0
werkzeug==3.1.3
pillow==11.1.0
requests==2.32.3
```

---

## config/vsftpd.conf

```conf
listen=YES
listen_ipv6=NO
anonymous_enable=NO
local_enable=YES
write_enable=YES
chroot_local_user=YES
allow_writeable_chroot=YES
local_root=/data/output

ssl_enable=YES
force_local_data_ssl=YES
force_local_logins_ssl=YES
ssl_cert_file=/etc/vsftpd/ssl/server.crt
ssl_key_file=/etc/vsftpd/ssl/server.key
require_ssl_reuse=NO
ssl_tlsv1=YES
ssl_sslv2=NO
ssl_sslv3=NO

pasv_enable=YES
pasv_min_port=30000
pasv_max_port=30010
pasv_address=0.0.0.0

userlist_enable=YES
userlist_file=/etc/vsftpd.userlist
userlist_deny=NO

log_ftp_protocol=YES
xferlog_enable=YES
xferlog_file=/var/log/vsftpd.log
```

---

## config/sshd_config

```conf
Port 22
Protocol 2
HostKey /etc/ssh/ssh_host_rsa_key
HostKey /etc/ssh/ssh_host_ecdsa_key
HostKey /etc/ssh/ssh_host_ed25519_key

PermitRootLogin no
PasswordAuthentication yes
PubkeyAuthentication no
ChallengeResponseAuthentication no
UsePAM yes

Subsystem sftp internal-sftp

AllowUsers tpcgtransfer
ChrootDirectory /data/output
X11Forwarding no
AllowTcpForwarding no
```

---

## scripts/entrypoint.sh

```bash
#!/bin/bash
set -e

# FTP/SFTP User anlegen
if [ -n "$SFTP_USER" ] && [ -n "$SFTP_PASSWORD" ]; then
  if ! id "$SFTP_USER" &>/dev/null; then
    useradd -m -d /data/output -s /usr/sbin/nologin "$SFTP_USER"
    echo "$SFTP_USER:$SFTP_PASSWORD" | chpasswd
  fi
  echo "$SFTP_USER" >> /etc/vsftpd.userlist
fi

# SSH starten
/usr/sbin/sshd

# vsftpd starten
/usr/sbin/vsftpd /etc/vsftpd/vsftpd.conf &

# Flask App starten
cd /app
exec /venv/bin/python -m flask --app app.main run --host 0.0.0.0 --port 8080
```

---

## app/main.py (Basisgerä°¼st)

Siehe Datei `app/main.py` im Repository.

---

## web/live/tpcg-live.html

Kopiere hier deine originale `tpcg-live.html` unverä°¤ndert hinein.

---

## docker-compose.yml

```yaml
services:
  hai-tpcg-cam-script:
    build: .
    container_name: hai-tpcg-cam-script
    restart: unless-stopped

    ports:
      - "8088:8080"
      - "2222:22"
      - "9900:990"
      - "30000-30010:30000-30010"

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

---

## .env.example

```env
TZ=Europe/Berlin

ADMIN_USER=admin
ADMIN_PASSWORD=CHANGE_ME_SECURE_PASSWORD
ADMIN_PASS_HASH=
API_KEY=CHANGE_ME_SECURE_API_KEY

SFTP_USER=tpcgtransfer
SFTP_PASSWORD=CHANGE_ME_SFTP_PASSWORD
FTPS_USER=tpcgtransfer
FTPS_PASSWORD=CHANGE_ME_FTPS_PASSWORD

PUBLIC_BASE_URL=https://cam.example.de
PROCESS_INTERVAL_SECONDS=30

OLLAMA_ENABLED=false
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llava
```

---

## .github/workflows/docker-publish.yml

```yaml
name: Build and publish GHCR image

on:
  push:
    branches:
      - main
    tags:
      - "v*"
  pull_request:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read
  packages: write

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  docker:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GitHub Container Registry
        if: github.event_name != 'pull_request'
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract Docker metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=tag
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push image
        uses: docker/build-push-action@v6
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## README.md

Siehe Datei `README.md` im Repository.
