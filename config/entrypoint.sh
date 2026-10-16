#!/bin/sh
set -e
mkdir -p /data/logs /data/input /data/output /data/scripts /data/backups /data/config
mkdir -p /var/run/vsftpd/empty /var/run/sshd
chown ftpuser:ftpuser /data 2>/dev/null || true
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
