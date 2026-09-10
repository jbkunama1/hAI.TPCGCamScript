# hAI.TPCGCamScript

Der Stack besteht aus zwei strikt getrennten Diensten:

- `hai-tpcgcamscript`: Flask, Gunicorn, Kamera-Worker und Live-Ausgabe.
- `hai-transfer`: gepinntes `drakkan/sftpgo:v2.7.5` für FTP, explizites FTPS und SFTP.

## SFTPGo-Datenbank-Fix

SFTPGo wird mit einem expliziten Konfigurations- und Datenpfad gestartet:

- Config: `/etc/sftpgo/sftpgo.json`.
- SQLite-Datenbank: `/var/lib/sftpgo/sftpgo.db`.
- Persistenz: `/opt/hai-tpcg-cam-script/data/transfer`.
- Webadmin: Host-Port `8081`.

Vor dem Deploy einmalig anlegen:

```bash
sudo mkdir -p \
  /opt/hai-tpcg-cam-script/data/input \
  /opt/hai-tpcg-cam-script/data/output \
  /opt/hai-tpcg-cam-script/data/scripts \
  /opt/hai-tpcg-cam-script/data/backups \
  /opt/hai-tpcg-cam-script/data/logs/transfer \
  /opt/hai-tpcg-cam-script/data/config \
  /opt/hai-tpcg-cam-script/data/transfer \
  /opt/hai-tpcg-cam-script/data/transfer-certs \
  /opt/hai-tpcg-cam-script/config/sftpgo

sudo chown -R 1000:1000 \
  /opt/hai-tpcg-cam-script/data/transfer \
  /opt/hai-tpcg-cam-script/data/logs/transfer
```

Die FTPS-Dateien müssen hier liegen:

```text
/opt/hai-tpcg-cam-script/data/transfer-certs/ftps.crt
/opt/hai-tpcg-cam-script/data/transfer-certs/ftps.key
```

Der Dienst startet mit `serve --config-dir /etc/sftpgo`; die SQLite-Datenbank wird nicht mehr relativ zum unbekannten Arbeitsverzeichnis gesucht.
