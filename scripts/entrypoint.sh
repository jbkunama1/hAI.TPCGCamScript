#!/bin/bash
set -e

LOG_DIR=/data/logs
mkdir -p "$LOG_DIR"
SERVER_LOG="$LOG_DIR/server.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$SERVER_LOG"
}

log "=== hAI.TPCGCamScript Container startet ==="
log "Ports: HTTP 8080 (extern 8067) | FTP 21 | SFTP 22 (extern 2222) | PASV 30000-30010"
log "SFTP_USER=${SFTP_USER:-<unset>} | Intervall=${PROCESS_INTERVAL_SECONDS:-30}s"

# Verarbeitungsskripte aufs Volume legen, falls noch nicht vorhanden
if [ -d /app/scripts-defaults ]; then
  for f in /app/scripts-defaults/*.py; do
    [ -e "/data/scripts/$(basename "$f")" ] || cp "$f" /data/scripts/
  done
fi

# FTP/SFTP User anlegen (Home = /data/input -> pure-ftpd chrooted dorthin)
if [ -n "$SFTP_USER" ] && [ -n "$SFTP_PASSWORD" ]; then
  if ! id "$SFTP_USER" &>/dev/null; then
    useradd -d /data/input -s /usr/sbin/nologin "$SFTP_USER" || true
    echo "$SFTP_USER:$SFTP_PASSWORD" | chpasswd
    log "FTP/SFTP-User '$SFTP_USER' angelegt (Home/Chroot: /data/input)"
  else
    usermod -d /data/input "$SFTP_USER" || true
    echo "$SFTP_USER:$SFTP_PASSWORD" | chpasswd
    log "FTP/SFTP-User '$SFTP_USER' existiert bereits (Home auf /data/input gesetzt, Passwort aktualisiert)"
  fi
else
  log "WARNUNG: SFTP_USER/SFTP_PASSWORD nicht gesetzt - kein FTP-User angelegt"
fi

# Upload-Unterordner vorbereiten: /data/input bleibt root:root (sshd-Chroot),
# die Unterordner gehoeren dem Transfer-User, damit die Kameras schreiben koennen
mkdir -p /data/input/tennis /data/input/padel
if id "$SFTP_USER" &>/dev/null; then
  chown -R "$SFTP_USER":"$SFTP_USER" /data/input/tennis /data/input/padel || true
fi
log "Upload-Ziele vorbereitet: /data/input/tennis + /data/input/padel (beschreibbar fuer ${SFTP_USER:-<unset>})"

# SSH/SFTP starten (Log direkt in Datei, da kein Syslog im Container laeuft)
/usr/sbin/sshd -E /data/logs/sshd.log
log "SFTP/SSH-Server gestartet (Port 22, Chroot: /data/input, Log: sshd.log)"

# pure-ftpd starten: komplette Konfiguration per Flags (keine Config-Datei,
# kein PAM; Startfehler landen vor dem Daemonisieren auf stderr -> ftpd-start.log)
FTP_ARGS="-l unix -A -E -b -p 30000:30010 -O w3c:$LOG_DIR/ftp-xfer.log"
if [ -n "$PASV_ADDRESS" ]; then
  FTP_ARGS="$FTP_ARGS -P $PASV_ADDRESS"
  log "PASV_ADDRESS gesetzt: $PASV_ADDRESS"
fi
if [ "${FTP_ALLOW_PLAIN:-false}" = "true" ]; then
  FTP_ARGS="$FTP_ARGS --tls=1"
  log "WARNUNG: Klartext-FTP erlaubt (FTP_ALLOW_PLAIN=true; TLS optional verfuegbar)"
else
  FTP_ARGS="$FTP_ARGS --tls=2"
fi

/usr/sbin/pure-ftpd $FTP_ARGS >> "$LOG_DIR/ftpd-start.log" 2>&1 &
sleep 2
# Lebenszeichen-Check per Bash-Builtin /dev/tcp (ss/iproute2 ist im Slim-Image nicht installiert).
# Hinweis: ein LEERES ftpd-start.log ist normal - pure-ftpd daemonisiert sich und schliesst stderr.
if (exec 3<>/dev/tcp/127.0.0.1/21) 2>/dev/null; then
  exec 3>&- 3<&-
  log "FTP-Server (pure-ftpd) gestartet: Port 21, PASV 30000-30010, Upload-Ziel /data/input (Log: ftpd-start.log / ftp-xfer.log)"
else
  log "FEHLER: pure-ftpd lauscht nach dem Start nicht auf Port 21 - Details: $LOG_DIR/ftpd-start.log"
fi

# Worker im Hintergrund starten
export PROCESS_INTERVAL_SECONDS="${PROCESS_INTERVAL_SECONDS:-30}"
/venv/bin/python /app/app/camera_worker.py &
log "Camera-Worker gestartet (Intervall ${PROCESS_INTERVAL_SECONDS}s, Log: worker.log)"

# Gunicorn fuer Flask-App starten
cd /app
log "Starte Gunicorn (3 Worker) auf 0.0.0.0:8080 - Access-Log: gunicorn-access.log"
exec /venv/bin/gunicorn -w 3 -b 0.0.0.0:8080 \
  --access-logfile /data/logs/gunicorn-access.log \
  --error-logfile - \
  --capture-output \
  app.main:app
