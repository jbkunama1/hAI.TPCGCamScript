FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    openssh-server pure-ftpd \
    libjpeg-dev zlib1g-dev \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# SSH
RUN mkdir -p /run/sshd
RUN ssh-keygen -A

# pure-ftpd: nologin-Shell fuer /etc/shells freigeben (sonst verweigert unix-Auth den Login)
RUN grep -qxF /usr/sbin/nologin /etc/shells || echo /usr/sbin/nologin >> /etc/shells

# pure-ftpd TLS-Zertifikat (Key + Cert in einer pem, wie pure-ftpd es erwartet)
RUN mkdir -p /etc/ssl/private \
    && openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout /tmp/pureftpd.key -out /tmp/pureftpd.crt -subj "/CN=tpcg-cam-script" \
    && cat /tmp/pureftpd.key /tmp/pureftpd.crt > /etc/ssl/private/pure-ftpd.pem \
    && rm /tmp/pureftpd.key /tmp/pureftpd.crt \
    && chmod 600 /etc/ssl/private/pure-ftpd.pem

COPY config/sshd_config /etc/ssh/sshd_config

WORKDIR /app
COPY requirements.txt .
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY scripts/ ./scripts/
COPY web/ ./web/

# Assets (Logos, Platzhalter, Original-CSS/JS) aus _original ins Image uebernehmen
COPY _original/tpc_logo_75px.jpg _original/letsnetz.jpg _original/platzhalter.jpg ./web/assets/
# jquery.js wird nicht mehr ins Image kopiert – Einbindung erfolgt per CDN
COPY _original/webcam.css _original/webcam.js ./web/assets/

# Verarbeitungsskripte als Vorlagen ins Image (Entrypoint kopiert sie aufs
# gemountete /data/scripts-Volume, falls dort noch keine Dateien liegen)
RUN mkdir -p /app/scripts-defaults
COPY scripts/process_single.py scripts/process_pair.py /app/scripts-defaults/

RUN chmod +x scripts/*.sh

EXPOSE 21 22 8080

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
