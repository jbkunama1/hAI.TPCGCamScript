import os
import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

DATA_ROOT = Path(os.getenv("DATA_ROOT", "/data"))
INPUT_DIR = DATA_ROOT / "input"
OUTPUT_DIR = DATA_ROOT / "output"
LOGS_DIR = DATA_ROOT / "logs"
CONFIG_DIR = DATA_ROOT / "config"

STATUS_FILE = OUTPUT_DIR / "status.json"

TENNIS_MIN_SIZE = 80000      # Bytes, wie in webcambilder-aktualisieren.php
PADEL_MIN_SIZE = 20000       # Bytes fuer Padel-Bilder
TENNIS_TARGET_SIZE = (896, 672)
TENNIS_CROP_SIZE = (896, 504)
PADEL_TARGET_SIZE = (896, 504)

# Routine-Log nur alle N Sekunden (Erfolg/Fehler wird sofort geloggt)
WORKER_LOG_INTERVAL = int(os.getenv("WORKER_LOG_INTERVAL_SECONDS", "120"))
# Log-Zeilen aelter als N Stunden werden entfernt
LOG_RETENTION_HOURS = int(os.getenv("LOG_RETENTION_HOURS", "48"))
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(5 * 1024 * 1024)))
LOG_KEEP_LINES = 5000

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("tpcg-worker")
logger.setLevel(logging.INFO)
_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
if not logger.handlers:
    _fh = logging.FileHandler(LOGS_DIR / "worker.log", encoding="utf-8")
    _fh.setFormatter(_formatter)
    logger.addHandler(_fh)
    _sh = logging.StreamHandler(sys.stdout)
    _sh.setFormatter(_formatter)
    logger.addHandler(_sh)

_last_summary_log = 0.0
_last_cleanup = 0.0

_TS_RE = re.compile(r"^\[?(\d{4}-\d{2}-\d{2})[ ,T](\d{2}:\d{2}:\d{2})")


def _line_ts(line):
    m = _TS_RE.match(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S").timestamp()
    except ValueError:
        return None


def cleanup_logs():
    """Entfernt Log-Zeilen aelter als LOG_RETENTION_HOURS und begrenzt Dateigroesse."""
    cutoff = time.time() - LOG_RETENTION_HOURS * 3600
    for f in sorted(LOGS_DIR.glob("*.log")):
        try:
            if f.stat().st_size > LOG_MAX_BYTES:
                lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
                f.write_text("\n".join(lines[-LOG_KEEP_LINES:]) + "\n", encoding="utf-8")
                logger.info("Log gekuerzt (> %d Bytes): %s auf letzte %d Zeilen", LOG_MAX_BYTES, f.name, LOG_KEEP_LINES)
                continue
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            if not lines:
                continue
            kept = []
            removed = 0
            for ln in lines:
                ts = _line_ts(ln)
                if ts is not None and ts < cutoff:
                    removed += 1
                else:
                    kept.append(ln)
            if removed:
                f.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
                logger.info("Log bereinigt: %s (%d Zeilen aelter als %dh entfernt)", f.name, removed, LOG_RETENTION_HOURS)
        except Exception as e:
            logger.warning("Log-Cleanup fuer %s fehlgeschlagen: %r", f.name, e)


def _ensure_dirs():
    for d in [INPUT_DIR, OUTPUT_DIR, LOGS_DIR, CONFIG_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    (OUTPUT_DIR / "tennis").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "padel").mkdir(parents=True, exist_ok=True)


def process_tennis():
    """
    Verarbeitet /data/input/tennis/webcam.jpg -> /data/output/tennis/webcam_live.jpg
    mit Resize und Crop gemaess der PHP-Logik.
    """
    _ensure_dirs()
    src_dir = INPUT_DIR / "tennis"
    dst_dir = OUTPUT_DIR / "tennis"
    src_file = src_dir / "webcam.jpg"
    dst_file = dst_dir / "webcam_live.jpg"

    if not src_file.exists():
        return {"processed": False, "reason": "no_source"}

    if not src_file.is_file():
        return {"processed": False, "reason": "not_a_file"}

    size = src_file.stat().st_size
    if size <= TENNIS_MIN_SIZE:
        return {"processed": False, "reason": f"file_too_small_{size}"}

    try:
        with Image.open(src_file) as img:
            resized = img.resize(TENNIS_TARGET_SIZE, Image.LANCZOS)
            cropped = resized.crop((0, 0, TENNIS_CROP_SIZE[0], TENNIS_CROP_SIZE[1]))
            dst_dir.mkdir(parents=True, exist_ok=True)
            cropped.save(dst_file, format="JPEG", quality=50, optimize=True)

        src_file.unlink(missing_ok=True)

        logger.info("Tennis: %s -> %s (%d Bytes Quelle)", src_file.name, dst_file, size)
        return {"processed": True, "output": str(dst_file)}

    except Exception as e:
        logger.exception("Tennis-Verarbeitung fehlgeschlagen: %r", e)
        return {"processed": False, "reason": f"error_{e!r}"}


def _collect_padel_candidates(today_dir: Path):
    if not today_dir.is_dir():
        return [], []

    padel_00 = []
    padel_01 = []

    for entry in sorted(today_dir.iterdir(), key=lambda p: p.name, reverse=True):
        if not entry.is_file():
            continue
        if entry.stat().st_size <= PADEL_MIN_SIZE:
            continue
        name = entry.name
        prefix = name[:8]
        if prefix == "Padel_00":
            padel_00.append(entry)
        elif prefix == "Padel_01":
            padel_01.append(entry)

    return padel_00, padel_01


def process_padel():
    _ensure_dirs()
    padel_root = INPUT_DIR / "padel"
    today_dir = padel_root / datetime.now().strftime("%Y/%m/%d")

    padel_00, padel_01 = _collect_padel_candidates(today_dir)
    if not padel_00 or not padel_01:
        return {"processed": False, "reason": "no_valid_padel_files"}

    src1 = padel_00[0]
    src2 = padel_01[0]

    dst_dir = OUTPUT_DIR / "padel"
    dst1 = dst_dir / "webcam1_live.jpg"
    dst2 = dst_dir / "webcam2_live.jpg"

    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(src1) as img1:
            resized1 = img1.resize(PADEL_TARGET_SIZE, Image.LANCZOS)
            resized1.save(dst1, format="JPEG", quality=50, optimize=True)
        with Image.open(src2) as img2:
            resized2 = img2.resize(PADEL_TARGET_SIZE, Image.LANCZOS)
            resized2.save(dst2, format="JPEG", quality=50, optimize=True)

        logger.info("Padel: %s + %s -> %s, %s", src1.name, src2.name, dst1, dst2)
        return {"processed": True, "output1": str(dst1), "output2": str(dst2)}

    except Exception as e:
        logger.exception("Padel-Verarbeitung fehlgeschlagen: %r", e)
        return {"processed": False, "reason": f"error_{e!r}"}


def write_status(last_tennis, last_padel):
    _ensure_dirs()
    status = {
        "last_run": datetime.now().isoformat(timespec="seconds"),
        "tennis": last_tennis,
        "padel": last_padel,
    }
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, indent=2), encoding="utf-8")


def _fmt(res):
    return "OK" if res.get("processed") else res.get("reason", "unknown")


def run_once():
    global _last_summary_log
    _ensure_dirs()
    tennis_result = process_tennis()
    padel_result = process_padel()
    write_status(tennis_result, padel_result)

    # Routine-Zeile nur alle WORKER_LOG_INTERVAL Sekunden; Erfolg/Fehler sofort
    now = time.time()
    has_output = tennis_result.get("processed") or padel_result.get("processed")
    has_error = _fmt(tennis_result).startswith("error_") or _fmt(padel_result).startswith("error_")
    if has_output or has_error or (now - _last_summary_log >= WORKER_LOG_INTERVAL):
        logger.info(
            "Verarbeitungslauf: tennis=%s | padel=%s",
            _fmt(tennis_result),
            _fmt(padel_result),
        )
        _last_summary_log = now
    return tennis_result, padel_result


def start_worker(interval_seconds: int = 30):
    """Endlos-Worker: Bilder aktualisieren + stuendliches Log-Cleanup."""
    global _last_cleanup
    _ensure_dirs()
    logger.info(
        "Camera-Worker gestartet: Intervall=%ss | Input=%s | Output=%s",
        interval_seconds, INPUT_DIR, OUTPUT_DIR,
    )
    logger.info(
        "Log-Policy: Routine-Zeile alle %ds | Aufbewahrung %dh | max %d Bytes",
        WORKER_LOG_INTERVAL, LOG_RETENTION_HOURS, LOG_MAX_BYTES,
    )
    cleanup_logs()
    _last_cleanup = time.time()
    while True:
        try:
            run_once()
            now = time.time()
            if now - _last_cleanup >= 3600:
                cleanup_logs()
                _last_cleanup = now
        except Exception as e:
            logger.exception("Fehler im Worker-Lauf: %r", e)
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            log_file = LOGS_DIR / "worker-errors.log"
            with log_file.open("a", encoding="utf-8") as fh:
                fh.write(f"[{datetime.now().isoformat()}] error: {e!r}\n")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    interval = int(os.getenv("PROCESS_INTERVAL_SECONDS", "30"))
    start_worker(interval_seconds=interval)
