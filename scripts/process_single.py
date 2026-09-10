# process_single.py
# Verarbeitet das neueste Bild aus /data/input (beliebiger Upload-Ordner)
# und schreibt das Ergebnis nach /data/output/eingang.jpg.
from pathlib import Path
from PIL import Image

INPUT_DIR = Path("/data/input")
OUTPUT_DIR = Path("/data/output")
OUT_FILE = OUTPUT_DIR / "eingang.jpg"


def latest_image(root: Path):
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def process():
    src = latest_image(INPUT_DIR)
    if src is None:
        print("Keine Eingabedatei gefunden")
        return
    img = Image.open(src)
    w, h = img.size
    size = min(w, h)
    left = (w - size) // 2
    top = (h - size) // 2
    cropped = img.crop((left, top, left + size, top + size))
    cropped = cropped.resize((512, 512))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cropped.save(OUT_FILE, quality=85)
    print(f"Processed {src} -> {OUT_FILE}")


if __name__ == "__main__":
    process()
