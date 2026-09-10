# SFTPGo-Transfer-Konfiguration

Diese Datei wird read-only nach `/etc/sftpgo/sftpgo.json` gemountet.

- FTP/explicit FTPS: Container-Port 2021.
- SFTP: Container-Port 2022.
- FTPS verwendet `/var/lib/sftpgo/certs/ftps.crt` und `ftps.key`.
- PASV: 30000–30010.
- `tls_mode=0` erlaubt normales FTP und explizites FTPS. Für Kameras ohne TLS bleibt FTP möglich; moderne Clients können STARTTLS/Explicit FTPS nutzen.

Lege die Zertifikatsdateien auf dem Host unter `/opt/hai-tpcg-cam-script/data/transfer-certs/` ab.
