"""Snapshot-Abruf (HTTP) als Alternative/Ergaenzung zum FTP-Upload.

Modus 'ftp': nichts wird geholt, Kameras laden per FTP hoch.
Modus 'snapshot': dieser Worker holt periodisch ein JPEG von einer URL
(z. B. Reolink cgi-bin/api.cgi?cmd=Snap) und legt es in /data/input ab.
Die Weiterverarbeitung uebernimmt unveraendert der camera_worker.

Start als Worker: python -m app.snapshot
"""

import base64
import json
import logging
import os
import random
import re
import ssl
import string
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from app import db

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
INPUT_DIR = DATA_DIR / "input"
LOGS_DIR = DATA_DIR / "logs"
CONFIG_DIR = DATA_DIR / "config"
STATUS_FILE = CONFIG_DIR / "snapshot_status.json"
TMP_FILE = CONFIG_DIR / "snapshot.tmp"

SETTING_KEY = "snapshot_config"
MASK = "********"
MIN_BYTES = 5000
MAX_BYTES = 15 * 1024 * 1024
KEEP_SNAPS = 3

TARGETS = {
    "tennis": "Tennis -> input/tennis/webcam.jpg",
    "padel_00": "Padel 00 -> input/padel/JJJJ/MM/TT/Padel_00_snap_*.jpg",
    "padel_01": "Padel 01 -> input/padel/JJJJ/MM/TT/Padel_01_snap_*.jpg",
}

DEFAULTS = {
    "mode": "ftp",
    "source": "reolink",
    "host": "",
    "port": "",
    "https": False,
    "channel": 0,
    "user": "",
    "password": "",
    "url": "",
    "verify_tls": False,
    "interval": 60,
    "timeout": 15,
    "target": "tennis",
}

LOGS_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("tpcg-snapshot")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    _fh = RotatingFileHandler(LOGS_DIR / "snapshot.log", maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8")
    _fh.setFormatter(_fmt)
    logger.addHandler(_fh)
    _sh = logging.StreamHandler(sys.stdout)
    _sh.setFormatter(_fmt)
    logger.addHandler(_sh)


# ----------------- Konfiguration -----------------

def load_config():
    cfg = dict(DEFAULTS)
    raw = db.get_setting(SETTING_KEY)
    if raw:
        try:
            cfg.update(json.loads(raw))
        except ValueError:
            pass
    return cfg


def public_config(cfg):
    out = dict(cfg)
    out["password"] = MASK if cfg.get("password") else ""
    return out


def save_config(cfg, actor=None):
    # Direkt speichern (nicht ueber db.set_setting), damit das Passwort nicht im Audit-Log landet
    with db._connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (SETTING_KEY, json.dumps(cfg), db._now()),
        )
    db.add_audit(
        "snapshot_config",
        {"mode": cfg["mode"], "source": cfg["source"], "target": cfg["target"], "interval": cfg["interval"]},
        actor,
    )


def _int(value, name, lo, hi):
    try:
        n = int(str(value).strip())
    except ValueError:
        raise ValueError(f"{name} ist keine Zahl")
    if n < lo or n > hi:
        raise ValueError(f"{name} muss zwischen {lo} und {hi} liegen")
    return n


def sanitize(body, old):
    cfg = dict(old)
    mode = body.get("mode", cfg["mode"])
    if mode not in ("ftp", "snapshot"):
        raise ValueError("Modus ungueltig")
    source = body.get("source", cfg["source"])
    if source not in ("reolink", "custom"):
        raise ValueError("Quelle ungueltig")
    target = body.get("target", cfg["target"])
    if target not in TARGETS:
        raise ValueError("Ziel ungueltig")

    host = str(body.get("host", cfg["host"])).strip()
    host = re.sub(r"^https?://", "", host).strip("/")
    if host and not re.fullmatch(r"[A-Za-z0-9.\-:\[\]]+", host):
        raise ValueError("Host ungueltig")

    port = str(body.get("port", cfg["port"])).strip()
    if port:
        port = str(_int(port, "Port", 1, 65535))

    url = str(body.get("url", cfg["url"])).strip()
    if url and not re.match(r"^https?://", url):
        raise ValueError("URL muss mit http:// oder https:// beginnen")

    pw = body.get("password")
    if pw not in (None, "", MASK):
        cfg["password"] = str(pw)

    cfg.update({
        "mode": mode,
        "source": source,
        "target": target,
        "host": host,
        "port": port,
        "url": url,
        "user": str(body.get("user", cfg["user"])).strip(),
        "https": bool(body.get("https", cfg["https"])),
        "verify_tls": bool(body.get("verify_tls", cfg["verify_tls"])),
        "channel": _int(body.get("channel", cfg["channel"]), "Kanal", 0, 15),
        "interval": _int(body.get("interval", cfg["interval"]), "Intervall", 10, 3600),
    })

    if mode == "snapshot":
        if source == "reolink" and not cfg["host"]:
            raise ValueError("Fuer den Snapshot-Modus fehlt der Host")
        if source == "custom" and not cfg["url"]:
            raise ValueError("Fuer den Snapshot-Modus fehlt die URL")
    return cfg


# ----------------- Abruf -----------------

def build_url(cfg):
    if cfg["source"] == "custom":
        if not cfg["url"]:
            raise ValueError("Keine URL konfiguriert")
        return cfg["url"]
    if not cfg["host"]:
        raise ValueError("Kein Host konfiguriert")
    scheme = "https" if cfg["https"] else "http"
    hostport = cfg["host"] + (":" + str(cfg["port"]) if cfg["port"] else "")
    rs = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return (
        f"{scheme}://{hostport}/cgi-bin/api.cgi?cmd=Snap&channel={int(cfg['channel'])}&rs={rs}"
        f"&user={quote(cfg['user'], safe='')}&password={quote(cfg['password'], safe='')}"
    )


def _safe_host(url):
    try:
        return urlsplit(url).netloc.split("@")[-1]
    except Exception:
        return "?"


def target_path(target):
    now = datetime.now()
    if target == "tennis":
        return INPUT_DIR / "tennis" / "webcam.jpg", None
    prefix = "Padel_00" if target == "padel_00" else "Padel_01"
    day_dir = INPUT_DIR / "padel" / now.strftime("%Y/%m/%d")
    return day_dir / f"{prefix}_snap_{now.strftime('%H%M%S')}.jpg", prefix


def _result(ok, message, **extra):
    res = {"ok": ok, "message": message, "ts": datetime.now().isoformat(timespec="seconds")}
    res.update(extra)
    return res


def fetch_once(cfg, save=True):
    try:
        url = build_url(cfg)
    except ValueError as e:
        return _result(False, str(e))

    headers = {"User-Agent": "hAI-TPCG-Snapshot/1.0", "Accept": "image/jpeg,*/*"}
    if cfg["source"] == "custom" and cfg.get("user"):
        token = base64.b64encode(f"{cfg['user']}:{cfg.get('password', '')}".encode()).decode()
        headers["Authorization"] = "Basic " + token

    ctx = None
    if url.startswith("https"):
        ctx = ssl.create_default_context() if cfg.get("verify_tls") else ssl._create_unverified_context()

    host = _safe_host(url)
    t0 = time.time()
    try:
        with urlopen(Request(url, headers=headers), timeout=int(cfg.get("timeout", 15)), context=ctx) as r:
            data = r.read(MAX_BYTES + 1)
            ctype = r.headers.get("Content-Type", "")
    except HTTPError as e:
        return _result(False, f"{host}: HTTP {e.code}")
    except URLError as e:
        return _result(False, f"{host}: Verbindungsfehler ({e.reason})")
    except Exception as e:
        return _result(False, f"{host}: {e!r}")

    ms = int((time.time() - t0) * 1000)
    if len(data) > MAX_BYTES:
        return _result(False, f"{host}: Antwort groesser als {MAX_BYTES} Bytes")
    if not data.startswith(b"\xff\xd8"):
        snippet = re.sub(r"[^\x20-\x7e]", "", data[:120].decode("latin-1"))
        return _result(False, f"{host}: kein JPEG (Content-Type '{ctype}', Anfang: {snippet})")
    if len(data) < MIN_BYTES:
        return _result(False, f"{host}: JPEG zu klein ({len(data)} Bytes)")

    if not save:
        return _result(True, f"{host}: JPEG ok, {len(data)} Bytes in {ms} ms (Test, nicht gespeichert)", bytes=len(data))

    dest, prefix = target_path(cfg["target"])
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        TMP_FILE.write_bytes(data)
        os.replace(TMP_FILE, dest)
        if prefix:
            snaps = sorted(dest.parent.glob(f"{prefix}_snap_*.jpg"))
            for old in snaps[:-KEEP_SNAPS]:
                old.unlink(missing_ok=True)
    except Exception as e:
        return _result(False, f"Speichern fehlgeschlagen: {e!r}")

    rel = str(dest.relative_to(DATA_DIR))
    return _result(True, f"{host}: {len(data)} Bytes in {ms} ms -> {rel}", bytes=len(data), file=rel)


# ----------------- Status -----------------

def read_status():
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_status(res):
    st = read_status()
    st["last_run"] = res["ts"]
    st["ok"] = res["ok"]
    st["message"] = res["message"]
    st["bytes"] = res.get("bytes", 0)
    if res["ok"]:
        st["last_success"] = res["ts"]
        st["file"] = res.get("file", "")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(st), encoding="utf-8")


# ----------------- Flask-Routen -----------------

def register(app, require_auth, get_actor):
    from flask import jsonify, request

    @app.get("/api/snapshot")
    @require_auth
    def api_snapshot_get():
        return jsonify({"config": public_config(load_config()), "status": read_status(), "targets": TARGETS})

    @app.post("/api/snapshot")
    @require_auth
    def api_snapshot_save():
        body = request.get_json(silent=True) or {}
        try:
            cfg = sanitize(body, load_config())
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        save_config(cfg, get_actor())
        logger.info("Konfiguration gespeichert: Modus=%s Quelle=%s Ziel=%s Intervall=%ss",
                    cfg["mode"], cfg["source"], cfg["target"], cfg["interval"])
        return jsonify({"status": "saved", "config": public_config(cfg)})

    @app.post("/api/snapshot/test")
    @require_auth
    def api_snapshot_test():
        body = request.get_json(silent=True) or {}
        try:
            cfg = sanitize(body, load_config())
        except ValueError as e:
            return jsonify({"ok": False, "message": str(e)}), 400
        return jsonify(fetch_once(cfg, save=False))


# ----------------- Worker-Schleife -----------------

def run_loop():
    logger.info("Snapshot-Worker gestartet")
    last_run = 0.0
    last_ok = None
    last_log = 0.0
    while True:
        try:
            cfg = load_config()
            if cfg["mode"] == "snapshot":
                if time.time() - last_run >= max(10, int(cfg["interval"])):
                    last_run = time.time()
                    res = fetch_once(cfg, save=True)
                    write_status(res)
                    now = time.time()
                    if res["ok"] != last_ok or now - last_log >= 600:
                        if res["ok"]:
                            logger.info("Snapshot OK: %s", res["message"])
                        else:
                            logger.warning("Snapshot FEHLER: %s", res["message"])
                        last_ok = res["ok"]
                        last_log = now
            else:
                last_run = 0.0
                last_ok = None
        except Exception:
            logger.exception("Fehler im Snapshot-Worker")
        time.sleep(2)


if __name__ == "__main__":
    run_loop()
