# process_pair.py
# Kombiniert die beiden neuesten Bilder aus /data/input zu einem
# Side-by-side-Bild und schreibt es nach /data/output/lounge-centercourt.jpg.
from pathlib import Path
from PIL import Image

INPUT_DIR = Path("/data/input")
OUTPUT_DIR = Path("/data/output")
OUT_FILE = OUTPUT_DIR / "lounge-centercourt.jpg"


def latest_images(root: Path, count: int = 2):
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:count]


def process():
    files = latest_images(INPUT_DIR)
    if len(files) < 2:
        print("Weniger als 2 Eingabedateien gefunden")
        return
    src1, src2 = files[0], files[1]
    img1 = Image.open(src1).convert("RGB").resize((512, 512))
    img2 = Image.open(src2).convert("RGB").resize((512, 512))
    combined = Image.new("RGB", (1024, 512))
    combined.paste(img1, (0, 0))
    combined.paste(img2, (512, 0))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined.save(OUT_FILE, quality=85)
    print(f"Processed pair {src1}, {src2} -> {OUT_FILE}")


if __name__ == "__main__":
    process()
