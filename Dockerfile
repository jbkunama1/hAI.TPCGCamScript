FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

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
EXPOSE 8080
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
