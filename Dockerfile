FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    openssh-server vsftpd \
    libjpeg-dev zlib1g-dev \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# SSH
RUN mkdir -p /run/sshd
RUN ssh-keygen -A

# FTPS SSL
RUN mkdir -p /etc/vsftpd/ssl
RUN openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout /etc/vsftpd/ssl/server.key \
    -out /etc/vsftpd/ssl/server.crt \
    -subj "/CN=tpcg-cam-script"

COPY config/vsftpd.conf /etc/vsftpd/vsftpd.conf
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

RUN chmod +x scripts/*.sh

EXPOSE 21 22 990 8080

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
