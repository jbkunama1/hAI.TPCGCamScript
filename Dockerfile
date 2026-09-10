FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    libjpeg-dev zlib1g-dev \
    vsftpd openssh-server supervisor \
    && rm -rf /var/lib/apt/lists/*

# Setup FTP/SFTP
RUN mkdir -p /var/run/vsftpd/empty /var/run/sshd /data/input /data/output /data/scripts /data/backups /data/logs /data/config
RUN useradd -m -d /data -s /bin/bash ftpuser && echo "ftpuser:password" | chpasswd

WORKDIR /app
COPY requirements.txt .
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY web/ ./web/
COPY _original/tpc_logo_75px.jpg _original/letsnetz.jpg _original/platzhalter.jpg ./web/assets/
COPY _original/webcam.css _original/webcam.js ./web/assets/
RUN mkdir -p /app/scripts-defaults
COPY scripts/process_single.py scripts/process_pair.py /app/scripts-defaults/
RUN chmod +x scripts/*.sh
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY config/vsftpd.conf /etc/vsftpd.conf

EXPOSE 8080 21 22 30000-30010
ENTRYPOINT ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
