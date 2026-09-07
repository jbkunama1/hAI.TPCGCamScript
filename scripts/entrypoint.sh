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
