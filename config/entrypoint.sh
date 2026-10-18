#!/bin/sh
set -e

mkdir -p /data/logs /data/input/tennis /data/input/padel /data/output /data/scripts /data/backups /data/config
mkdir -p /var/run/vsftpd/empty /var/run/sshd

# FTP/FTPS/SFTP-Zugang aus der Umgebung (Aliase werden der Reihe nach geprueft)
FTP_U="${FTP_USER:-${FTP_USERNAME:-${FTPUSER:-${TRANSFER_USER:-ftpuser}}}}"
FTP_P="${FTP_PASS:-${FTP_PASSWORD:-${FTPPASS:-${TRANSFER_PASSWORD:-}}}}"

if ! echo "$FTP_U" | grep -Eq '^[a-z_][a-z0-9_-]{0,31}$'; then
  echo "[entrypoint] ungueltiger FTP-Benutzername '$FTP_U' - verwende ftpuser"
  FTP_U=ftpuser
fi
if [ -z "$FTP_P" ]; then
  echo "[entrypoint] WARNUNG: kein FTP-Passwort in der Umgebung (FTP_PASS) - Standardpasswort 'password' ist aktiv"
  FTP_P=password
fi

if ! id "$FTP_U" >/dev/null 2>&1; then
  useradd -M -d /data -s /bin/bash "$FTP_U"
fi
printf '%s:%s\n' "$FTP_U" "$FTP_P" | chpasswd
if [ "$FTP_U" != "ftpuser" ]; then
  usermod -L ftpuser 2>/dev/null || true
fi
sed -i "s/^AllowUsers.*/AllowUsers $FTP_U/" /etc/ssh/sshd_config
echo "[entrypoint] FTP/SFTP-Benutzer: $FTP_U"

# sshd-Chroot (/data/input) verlangt root-Besitz fuer /data und /data/input;
# beschreibbar fuer den FTP-Benutzer sind nur die Unterordner
chown root:root /data /data/input
chmod 755 /data /data/input
chown -R "$FTP_U":"$FTP_U" /data/input/tennis /data/input/padel

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
