#!/bin/bash
set -e

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
  fi
  echo "$SFTP_USER" >> /etc/vsftpd.userlist
fi

# SSH starten
/usr/sbin/sshd

# vsftpd starten
/usr/sbin/vsftpd /etc/vsftpd/vsftpd.conf &

# Worker im Hintergrund starten
export PROCESS_INTERVAL_SECONDS="${PROCESS_INTERVAL_SECONDS:-30}"
/venv/bin/python /app/app/camera_worker.py &

# Gunicorn für Flask-App starten
cd /app
exec /venv/bin/gunicorn -w 3 -b 0.0.0.0:8080 app.main:app
