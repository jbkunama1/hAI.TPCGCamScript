#!/bin/bash
set -e

LOG_DIR=/data/logs
mkdir -p "$LOG_DIR"
SERVER_LOG="$LOG_DIR/server.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$SERVER_LOG"
}

log "=== hAI.TPCGCamScript Container startet ==="
log "Ports: HTTP 8080 (extern 8067) | FTP 21 | FTPS 990 (extern 9900) | SFTP 22 (extern 2222)"
log "SFTP_USER=${SFTP_USER:-<unset>} | FTPS_USER=${FTPS_USER:-<unset>} | Intervall=${PROCESS_INTERVAL_SECONDS:-30}s"

# FTP/SFTP User anlegen
if [ -n "$SFTP_USER" ] && [ -n "$SFTP_PASSWORD" ]; then
  if ! id "$SFTP_USER" &>/dev/null; then
    # Chroot-Basis /data/sftp, darunter ein beschreibbarer Ordner output
    mkdir -p /data/sftp/output
    chown root:root /data/sftp
    chmod 755 /data/sftp

    useradd -d /data/sftp/output -s /usr/sbin/nologin "$SFTP_USER" || true
    echo "$SFTP_USER:$SFTP_PASSWORD" | chpasswd

    chown "$SFTP_USER":"$SFTP_USER" /data/sftp/output || true
    log "FTP/SFTP-User '$SFTP_USER' angelegt"
  else
    log "FTP/SFTP-User '$SFTP_USER' existiert bereits"
  fi
  echo "$SFTP_USER" >> /etc/vsftpd.userlist
else
  log "WARNUNG: SFTP_USER/SFTP_PASSWORD nicht gesetzt - kein FTP-User angelegt"
fi

# SSH/SFTP starten (Log direkt in Datei, da kein Syslog im Container laeuft)
/usr/sbin/sshd -E /data/logs/sshd.log
log "SFTP/SSH-Server gestartet (Port 22, Log: sshd.log)"

# vsftpd starten
/usr/sbin/vsftpd /etc/vsftpd/vsftpd.conf &
log "FTP/FTPS-Server gestartet (Ports 21 + 990, Logs: vsftpd.log / vsftpd-xfer.log)"

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
