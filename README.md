# hAI.TPCGCamScript

Der Stack besteht aus zwei strikt getrennten Diensten:

- `hai-tpcgcamscript`: Flask, Gunicorn, Kamera-Worker und Live-Ausgabe.
- `hai-transfer`: fertiger SFTPGo-Container für **FTP, explizites FTPS und SFTP**.

Der Hauptcontainer enthält keinerlei FTP-, FTPS- oder SFTP-Server, keine SSH-Konfiguration, keine Transfer-Benutzer und keine Transfer-Ports.

## Ports

| Dienst | Host-Port | Container-Port |
|---|---:|---:|
| Web/API | 8067 | 8080 |
| FTP | 21 | 2021 |
| Explizites FTPS | 21 | 2021 |
| SFTP | 2222 | 2022 |
| SFTPGo-Webadmin | nicht veröffentlicht | 8080 |
| PASV-Datenkanal | 30000–30010 | 30000–30010 |

Für die Fritzbox: extern `521 -> 21` und `30000–30010 -> 30000–30010`. `PASV_ADDRESS` muss die öffentliche IP oder der öffentliche Hostname sein.

## Host-Verzeichnisse

```bash
sudo mkdir -p \
  /opt/hai-tpcg-cam-script/data/input \
  /opt/hai-tpcg-cam-script/data/output \
  /opt/hai-tpcg-cam-script/data/scripts \
  /opt/hai-tpcg-cam-script/data/backups \
  /opt/hai-tpcg-cam-script/data/logs/transfer \
  /opt/hai-tpcg-cam-script/data/config \
  /opt/hai-tpcg-cam-script/data/transfer
```

## SFTPGo-Erstkonfiguration

Nach dem ersten Start den SFTPGo-Webadmin lokal über den Docker-Netzwerkpfad bzw. einen temporären Port-Tunnel öffnen und einen Benutzer anlegen:

- Benutzer-Home: `/srv/sftpgo/input`
- FTP erlauben.
- SFTP erlauben.
- Passwort oder SSH-Key setzen.
- Schreibrechte auf den benötigten Unterordnern aktivieren.
- FTPS bei Bedarf mit einem Zertifikat in SFTPGo aktivieren.

Die Zugangsdaten für den Transferdienst sind bewusst getrennt von den Web/API-Administratordaten.

## Deployment

1. Externes Netzwerk erstellen, falls erforderlich:

```bash
docker network create highfishNetwork
```

2. Portainer-Variablen setzen:

```text
ADMIN_PASSWORD=...
API_KEY=...
TRANSFER_ADMIN_PASSWORD=...
PASV_ADDRESS=dein.public.hostname
```

3. Stack aus `docker-compose.yml` deployen.
4. SFTPGo-Benutzer im Transfer-Container anlegen.
5. Erst danach die Fritzbox-Weiterleitungen aktivieren.

## Migration

Der frühere integrierte vsftpd/pure-ftpd-Stack wird nicht mehr verwendet. Im Hauptcontainer gibt es keine FTP-/FTPS-/SFTP-Startlogik und kein `sshd` mehr. Alle Transfer-Logs und die Transfer-Konfiguration liegen im `hai-transfer`-Container beziehungsweise unter `/data/transfer` und `/data/logs/transfer`.
