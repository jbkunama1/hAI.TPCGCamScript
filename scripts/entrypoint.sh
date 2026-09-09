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

# Upload-Unterordner vorbereiten: /data/input bleibt root:root (sshd-Chroot),
# die Unterordner gehoeren dem Transfer-User, damit die Kameras schreiben koennen
mkdir -p /data/input/tennis /data/input/padel
if id "$SFTP_USER" &>/dev/null; then
  chown -R "$SFTP_USER":"$SFTP_USER" /data/input/tennis /data/input/padel || true
fi
log "Upload-Ziele vorbereitet: /data/input/tennis + /data/input/padel (beschreibbar fuer ${SFTP_USER:-<unset>})"

# Passive FTP-Adresse fuer externe Clients (Router-Portweiterleitung)
if [ -n "$PASV_ADDRESS" ]; then
  sed -i "s/^pasv_address=.*/pasv_address=${PASV_ADDRESS}/" /etc/vsftpd/vsftpd.conf
  log "PASV_ADDRESS gesetzt: $PASV_ADDRESS"
fi

# Optionaler Klartext-Fallback (nur falls die Kamera kein explizites FTPS kann)
if [ "${FTP_ALLOW_PLAIN:-false}" = "true" ]; then
  sed -i "s/^force_local_logins_ssl=.*/force_local_logins_ssl=NO/" /etc/vsftpd/vsftpd.conf
  sed -i "s/^force_local_data_ssl=.*/force_local_data_ssl=NO/" /etc/vsftpd/vsftpd.conf
  log "WARNUNG: Klartext-FTP erlaubt (FTP_ALLOW_PLAIN=true) - nur fuer Kameras ohne explizites FTPS"
fi

# SSH/SFTP starten (Log direkt in Datei, da kein Syslog im Container laeuft)
/usr/sbin/sshd -E /data/logs/sshd.log
log "SFTP/SSH-Server gestartet (Port 22, Chroot: /data/input, Log: sshd.log)"

# vsftpd starten
/usr/sbin/vsftpd /etc/vsftpd/vsftpd.conf &
log "FTP/FTPS-Server gestartet (Ports 21 + 990, Upload-Ziel: /data/input, Logs: vsftpd.log / vsftpd-xfer.log)"

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
