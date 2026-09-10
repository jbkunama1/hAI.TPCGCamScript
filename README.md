# hAI.TPCGCamScript

Der Stack besteht aus zwei strikt getrennten Diensten:

- `hai-tpcgcamscript`: Flask, Gunicorn, Kamera-Worker und Live-Ausgabe.
- `hai-transfer`: gepinntes `drakkan/sftpgo:v2.7.5` für FTP, explizites FTPS und SFTP.

## SFTPGo-Start

Der Transfer-Container startet die Binary explizit:

```yaml
entrypoint: ["/usr/bin/sftpgo"]
command: ["serve", "--config-dir", "/etc/sftpgo"]
```

Damit wird `serve` als Unterkommando von `/usr/bin/sftpgo` ausgeführt und nicht mehr als eigenständige Datei gesucht.

## SFTPGo-Datenbank

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
