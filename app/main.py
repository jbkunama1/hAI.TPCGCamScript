import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory, redirect, make_response
from werkzeug.security import check_password_hash

app = Flask(__name__)

# Konfiguration aus Environment
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH", "")
API_KEY = os.getenv("API_KEY", "")

# Pfade
BASE_DIR = Path("/app")
DATA_DIR = Path("/data")
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
SCRIPTS_DIR = DATA_DIR / "scripts"
BACKUPS_DIR = DATA_DIR / "backups"
LOGS_DIR = DATA_DIR / "logs"

LIVE_PAGE = BASE_DIR / "web" / "live" / "tpcg-live.html"
SCRIPT_SINGLE = SCRIPTS_DIR / "process_single.py"
SCRIPT_PAIR = SCRIPTS_DIR / "process_pair.py"

# Sicherstellen, dass Verzeichnisse existieren
for d in [INPUT_DIR, OUTPUT_DIR, SCRIPTS_DIR, BACKUPS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Initiale Skripte, falls nicht vorhanden
DEFAULT_SINGLE = """# process_single.py
from pathlib import Path
from PIL import Image

INPUT_DIR = Path("/data/input")
OUTPUT_DIR = Path("/data/output")

def process():
    files = list(INPUT_DIR.glob("*.jpg")) + list(INPUT_DIR.glob("*.png"))
    if not files:
        return
    src = files[0]
    img = Image.open(src)
    w, h = img.size
    size = min(w, h)
    left = (w - size) // 2
    top = (h - size) // 2
    right = left + size
    bottom = top + size
    cropped = img.crop((left, top, right, bottom))
    cropped = cropped.resize((512, 512))
    out = OUTPUT_DIR / "eingang.jpg"
    cropped.save(out, quality=85)
    print(f"Processed {src} -> {out}")

if __name__ == "__main__":
    process()
"""

DEFAULT_PAIR = """# process_pair.py
from pathlib import Path
from PIL import Image

INPUT_DIR = Path("/data/input")
OUTPUT_DIR = Path("/data/output")

def process():
    files = sorted(list(INPUT_DIR.glob("*.jpg")) + list(INPUT_DIR.glob("*.png")))
    if len(files) < 2:
        return
    src1, src2 = files[0], files[1]
    img1 = Image.open(src1).convert("RGB")
    img2 = Image.open(src2).convert("RGB")
    img1 = img1.resize((512, 512))
    img2 = img2.resize((512, 512))
    combined = Image.new("RGB", (1024, 512))
    combined.paste(img1, (0, 0))
    combined.paste(img2, (512, 0))
    out = OUTPUT_DIR / "lounge-centercourt.jpg"
    combined.save(out, quality=85)
    print(f"Processed pair {src1}, {src2} -> {out}")

if __name__ == "__main__":
    process()
"""

if not SCRIPT_SINGLE.exists():
    SCRIPT_SINGLE.write_text(DEFAULT_SINGLE)
if not SCRIPT_PAIR.exists():
    SCRIPT_PAIR.write_text(DEFAULT_PAIR)

# ----------------- Auth -----------------

def _unauthorized_response():
    resp = make_response(jsonify({"error": "Unauthorized"}), 401)
    resp.headers["WWW-Authenticate"] = 'Basic realm="TPCG Admin"'
    return resp


def check_basic_auth():
    auth = request.authorization
    if not auth or auth.type != "basic":
        return False
    if auth.username != ADMIN_USER:
        return False
    if ADMIN_PASS_HASH:
        return check_password_hash(ADMIN_PASS_HASH, auth.password)
    return auth.password == ADMIN_PASSWORD


def require_auth(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not check_basic_auth():
            return _unauthorized_response()
        return f(*args, **kwargs)

    return wrapper


def require_api_key(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if key == API_KEY:
            return f(*args, **kwargs)
        if check_basic_auth():
            return f(*args, **kwargs)
        return _unauthorized_response()

    return wrapper

# ----------------- Helpers -----------------

def write_audit_log(action, details):
    log_file = LOGS_DIR / "audit.jsonl"
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "details": details,
    }
    with log_file.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def backup_script(path: Path):
    if not path.exists():
        return
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    backup_name = f"{path.stem}-{ts}{path.suffix}"
    backup_path = BACKUPS_DIR / backup_name
    backup_path.write_bytes(path.read_bytes())


def validate_python_code(code: str):
    import tempfile
    import subprocess
    import sys

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", tmp_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return False, result.stderr
        return True, ""
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ----------------- Routes -----------------

@app.get("/")
@require_auth
def dashboard():
    # Nach erfolgreicher Auth direkt auf die Live-Seite weiterleiten
    return redirect("/live")


@app.get("/live")
def live_preview():
    return send_file(LIVE_PAGE, mimetype="text/html")


@app.get("/output/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.get("/api/status")
@require_api_key
def api_status():
    return jsonify({"service": "hAI.TPCGCamScript", "status": "running"})


@app.get("/api/scripts")
@require_auth
def list_scripts():
    scripts = []
    for p in SCRIPTS_DIR.glob("*.py"):
        scripts.append(
            {
                "name": p.name,
                "size": p.stat().st_size,
                "modified": datetime.utcfromtimestamp(p.stat().st_mtime).isoformat()
                + "Z",
            }
        )
    return jsonify({"scripts": scripts})


@app.get("/api/scripts/<name>")
@require_auth
def get_script(name):
    path = SCRIPTS_DIR / name
    if not path.exists() or not name.endswith(".py"):
        return jsonify({"error": "Script not found"}), 404
    return jsonify({"name": name, "code": path.read_text()})


@app.post("/api/scripts/<name>")
@require_auth
def save_script(name):
    path = SCRIPTS_DIR / name
    if not name.endswith(".py"):
        return jsonify({"error": "Invalid filename"}), 400

    body = request.get_json(silent=True) or {}
    code = body.get("code", "")

    ok, err = validate_python_code(code)
    if not ok:
        return jsonify({"error": "Invalid Python code", "details": err}), 400

    if path.exists():
        backup_script(path)

    path.write_text(code)
    write_audit_log("script_save", {"name": name, "size": len(code)})

    return jsonify({"status": "saved", "name": name})


@app.post("/api/scripts/<name>/run")
@require_auth
def run_script(name):
    path = SCRIPTS_DIR / name
    if not path.exists() or not name.endswith(".py"):
        return jsonify({"error": "Script not found"}), 404

    import subprocess
    import sys

    try:
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        log_entry = {
            "script": name,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        (LOGS_DIR / "script_runs.jsonl").open("a").write(
            json.dumps(log_entry) + "\n"
        )
        return jsonify(log_entry)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Script timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/logs")
@require_auth
def get_logs():
    log_file = LOGS_DIR / "app.log"
    if not log_file.exists():
        return jsonify({"lines": []})
    lines = log_file.read_text().splitlines()[-200:]
    return jsonify({"lines": lines})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
