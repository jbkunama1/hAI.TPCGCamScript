#!/bin/bash
set -e

LOG_DIR=/data/logs
mkdir -p "$LOG_DIR"
SERVER_LOG="$LOG_DIR/server.log"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$SERVER_LOG"
}

log "=== hAI.TPCGCamScript Container startet ==="
log "Port: HTTP 8080 (extern 8067) | FTP/FTPS/SFTP: separater hai-transfer-Container"
log "Intervall=${PROCESS_INTERVAL_SECONDS:-30}s"

if [ -d /app/scripts-defaults ]; then
  for f in /app/scripts-defaults/*.py; do
    [ -e "/data/scripts/$(basename "$f")" ] || cp "$f" /data/scripts/
  done
fi

export PROCESS_INTERVAL_SECONDS="${PROCESS_INTERVAL_SECONDS:-30}"
/venv/bin/python /app/app/camera_worker.py &
log "Camera-Worker gestartet (Intervall ${PROCESS_INTERVAL_SECONDS}s, Log: worker.log)"

cd /app
log "Starte Gunicorn (3 Worker) auf 0.0.0.0:8080 - Access-Log: gunicorn-access.log"
exec /venv/bin/gunicorn -w 3 -b 0.0.0.0:8080 \
  --access-logfile /data/logs/gunicorn-access.log \
  --error-logfile - \
  --capture-output \
  app.main:app
