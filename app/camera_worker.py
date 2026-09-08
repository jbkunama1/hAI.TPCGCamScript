import os
import json
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

TENnis_MIN_SIZE = 80000      # Bytes, wie in webcambilder-aktualisieren.php
PADEL_MIN_SIZE = 20000       # Bytes für Padel-Bilder
TENnis_TARGET_SIZE = (896, 672)
TENnis_CROP_SIZE = (896, 504)
PADEL_TARGET_SIZE = (896, 504)


def _ensure_dirs():
    for d in [INPUT_DIR, OUTPUT_DIR, LOGS_DIR, CONFIG_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    (OUTPUT_DIR / "tennis").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "padel").mkdir(parents=True, exist_ok=True)


def process_tennis():
    """
    Verarbeitet /data/input/tennis/webcam.jpg → /data/output/tennis/webcam_live.jpg
    mit Resize und Crop gemäß deiner PHP-Logik.
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
    if size <= TENnis_MIN_SIZE:
        return {"processed": False, "reason": f"file_too_small_{size}"}

    try:
        with Image.open(src_file) as img:
            # Resize auf 896x672
            resized = img.resize(TENnis_TARGET_SIZE, Image.LANCZOS)

            # Crop auf 896x504 (oberer Teil)
            cropped = resized.crop((0, 0, TENnis_CROP_SIZE[0], TENnis_CROP_SIZE[1]))

            dst_dir.mkdir(parents=True, exist_ok=True)
            cropped.save(dst_file, format="JPEG", quality=50, optimize=True)

        # Originalaufnahme löschen wie in PHP
        src_file.unlink(missing_ok=True)

        return {"processed": True, "output": str(dst_file)}

    except Exception as e:
        return {"processed": False, "reason": f"error_{e!r}"}


def _collect_padel_candidates(today_dir: Path):
    """
    Sucht im heutigen Padel-Ordner nach gültigen Dateien und trennt sie
    in Arrays für Padel_00 und Padel_01, wie in deiner PHP-Implementierung.
    """
    if not today_dir.is_dir():
        return [], []

    padel_00 = []
    padel_01 = []

    # Absteigend sortiert, damit der aktuellste Zeitstempel zuerst kommt
    for entry in sorted(today_dir.iterdir(), key=lambda p: p.name, reverse=True):
        if not entry.is_file():
            continue

        # Mindestgröße prüfen (Upload beginnt mit 0 Bytes)
        if entry.stat().st_size <= PADEL_MIN_SIZE:
            continue

        name = entry.name
        prefix = name[:8]  # "Padel_00" oder "Padel_01"

        if prefix == "Padel_00":
            padel_00.append(entry)
        elif prefix == "Padel_01":
            padel_01.append(entry)

    return padel_00, padel_01


def process_padel():
    """
    Verarbeitet die neuesten Dateien Padel_00_* / Padel_01_* im heutigen
    Ordner zu /data/output/padel/webcam1_live.jpg und webcam2_live.jpg.
    """
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

        return {
            "processed": True,
            "output1": str(dst1),
            "output2": str(dst2),
        }

    except Exception as e:
        return {"processed": False, "reason": f"error_{e!r}"}


def write_status(last_tennis, last_padel):
    """
    Schreibt /data/output/status.json mit Zeitstempel und einfachem Status.
    """
    _ensure_dirs()
    status = {
        "last_run": datetime.now().isoformat(timespec="seconds"),
        "tennis": last_tennis,
        "padel": last_padel,
    }
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(status, indent=2), encoding="utf-8")


def run_once():
    _ensure_dirs()
    tennis_result = process_tennis()
    padel_result = process_padel()
    write_status(tennis_result, padel_result)
    return tennis_result, padel_result


def start_worker(interval_seconds: int = 30):
    """
    Endlos-Worker, der alle `interval_seconds` die Bilder aktualisiert.
    Diese Funktion kann z.B. aus app.main in einem Hintergrund-Thread
    gestartet werden.
    """
    _ensure_dirs()
    while True:
        try:
            run_once()
        except Exception as e:
            # Minimaler Fallback-Log: Fehler in eine einfache Datei schreiben
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            log_file = LOGS_DIR / "worker-errors.log"
            with log_file.open("a", encoding="utf-8") as fh:
                fh.write(f"[{datetime.now().isoformat()}] error: {e!r}\n")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    # Standalone-Ausführung: z.B. zum Testen
    interval = int(os.getenv("PROCESS_INTERVAL_SECONDS", "30"))
    start_worker(interval_seconds=interval)
