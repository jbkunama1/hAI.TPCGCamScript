# hAI.TPCGCamScript

Der Stack besteht aus zwei strikt getrennten Diensten:

- `hai-tpcgcamscript`: Flask, Gunicorn, Kamera-Worker und Live-Ausgabe.
- `hai-transfer`: gepinntes `drakkan/sftpgo:v2.7.5` für **FTP, explizites FTPS und SFTP**.

Der Hauptcontainer enthält keinerlei FTP-, FTPS- oder SFTP-Server, keine SSH-Konfiguration, keine Transfer-Benutzer und keine Transfer-Ports.

## Transfer-Stack

| Dienst | Host-Port | Container-Port |
|---|---:|---:|
| FTP + explizites FTPS | 21 | 2021 |
| SFTP | 2222 | 2022 |
| SFTPGo-Webadmin | 8081 | 8080 |
| PASV-Datenkanal | 30000–30010 | 30000–30010 |

Das Image ist bewusst auf `drakkan/sftpgo:v2.7.5` gepinnt. Ein Upgrade erfolgt kontrolliert durch eine Compose-Änderung, nicht automatisch durch `latest`.

## Fritzbox

- extern `521 -> 21`.
- extern `30000–30010 -> 30000–30010`.
- `PASV_ADDRESS` auf die öffentliche IP bzw. den öffentlichen Hostnamen setzen.
- Für SFTP extern `2222 -> 2222`.

## TLS-Zertifikat

SFTPGo nutzt explizites FTPS mit TLS 1.2 oder höher. Zertifikat und Schlüssel liegen außerhalb des Images:

```bash
sudo mkdir -p /opt/hai-tpcg-cam-script/data/transfer-certs
sudo chmod 700 /opt/hai-tpcg-cam-script/data/transfer-certs
sudo cp ftps.crt /opt/hai-tpcg-cam-script/data/transfer-certs/ftps.crt
sudo cp ftps.key /opt/hai-tpcg-cam-script/data/transfer-certs/ftps.key
sudo chmod 644 /opt/hai-tpcg-cam-script/data/transfer-certs/ftps.crt
sudo chmod 600 /opt/hai-tpcg-cam-script/data/transfer-certs/ftps.key
```

Das Zertifikat muss den öffentlichen FTP-Hostname abdecken. Für reine Kamera-Kompatibilität kann ein selbstsigniertes Zertifikat verwendet werden, moderne Clients sollten aber ein vertrauenswürdiges Zertifikat erhalten.

## Benutzer

Die Transfer-Benutzer werden in SFTPGo persistent unter `/opt/hai-tpcg-cam-script/data/transfer` gespeichert. Der erste Benutzer wird einmalig im SFTPGo-Webadmin angelegt:

- Webadmin: `http://SERVER-IP:8081`.
- Benutzername: Wert von `TRANSFER_USER`.
- Passwort: Wert von `TRANSFER_PASSWORD`.
- Home-Verzeichnis: `/srv/sftpgo/input`.
- Rechte: Liste, Download, Upload, Überschreiben, Löschen, Umbenennen und Verzeichnisse anlegen.
- FTP und SFTP aktivieren.

Passwörter gehören nicht ins Repository. `users.json.example` ist nur eine Feldvorlage.

## Host-Verzeichnisse

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
```

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
TRANSFER_USER=tpcgtransfer
TRANSFER_PASSWORD=...
PASV_ADDRESS=dein.public.hostname
```

3. Zertifikat und Schlüssel in `data/transfer-certs` ablegen.
4. Stack aus `docker-compose.yml` deployen.
5. SFTPGo-Webadmin öffnen und den Transfer-Benutzer anlegen bzw. prüfen.
6. Danach die Fritzbox-Weiterleitungen aktivieren.

## Migration

Der frühere integrierte vsftpd/pure-ftpd-Stack wird nicht mehr verwendet. Im Hauptcontainer gibt es keine FTP-/FTPS-/SFTP-Startlogik und kein `sshd` mehr. Alle Transfer-Logs und die Transfer-Konfiguration liegen im `hai-transfer`-Container beziehungsweise unter `/data/transfer` und `/data/logs/transfer`.
