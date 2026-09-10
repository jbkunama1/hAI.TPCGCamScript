import os
import json
import logging
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory, make_response
from werkzeug.security import check_password_hash

from app import db

APP_VERSION = os.getenv("APP_VERSION", "1.4.0")

app = Flask(__name__)

# Konfiguration aus Environment (Initial-Bootstrap; danach gilt die SQLite-DB)
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH", "")
API_KEY = os.getenv("API_KEY", "")

# Pfade
BASE_DIR = Path("/app")
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
SCRIPTS_DIR = DATA_DIR / "scripts"
BACKUPS_DIR = DATA_DIR / "backups"
LOGS_DIR = DATA_DIR / "logs"
CONFIG_DIR = DATA_DIR / "config"
LEGACY_THEME_FILE = CONFIG_DIR / "theme.json"

WEB_DIR = BASE_DIR / "web"
ASSETS_DIR = WEB_DIR / "assets"
LIVE_PAGE = WEB_DIR / "live" / "tpcg-live.html"
ADMIN_PAGE = WEB_DIR / "admin" / "theme-admin.html"
THEMES_DIR = WEB_DIR / "themes"

SCRIPT_SINGLE = SCRIPTS_DIR / "process_single.py"
SCRIPT_PAIR = SCRIPTS_DIR / "process_pair.py"

# Sicherstellen, dass Verzeichnisse existieren
for d in [INPUT_DIR, OUTPUT_DIR, SCRIPTS_DIR, BACKUPS_DIR, LOGS_DIR, CONFIG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ----------------- Logging -----------------

logger = logging.getLogger("tpcg")
logger.setLevel(logging.INFO)
_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
if not logger.handlers:
    _fh = logging.FileHandler(LOGS_DIR / "app.log", encoding="utf-8")
    _fh.setFormatter(_formatter)
    logger.addHandler(_fh)
    _sh = logging.StreamHandler(sys.stdout)
    _sh.setFormatter(_formatter)
    logger.addHandler(_sh)

# Log-Dateien, die ueber /api/logs abrufbar sind
LOG_FILES = {
    "app": "app.log",
    "server": "server.log",
    "worker": "worker.log",
    "worker-errors": "worker-errors.log",
    "vsftpd": "vsftpd.log",
    "vsftpd-xfer": "vsftpd-xfer.log",
    "vsftpd-start": "vsftpd-start.log",
    "sshd": "sshd.log",
    "gunicorn-access": "gunicorn-access.log",
}

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

# ----------------- Datenbank -----------------

db.init_db(ADMIN_USER, ADMIN_PASSWORD, ADMIN_PASS_HASH, LEGACY_THEME_FILE)

# ----------------- Auth -----------------

def _unauthorized_response():
    resp = make_response(jsonify({"error": "Unauthorized"}), 401)
    resp.headers["WWW-Authenticate"] = 'Basic realm="TPCG Admin"'
    return resp


def check_basic_auth():
    auth = request.authorization
    if not auth or auth.type != "basic":
        return False
    # 1) Datenbank-Benutzer (persistent, ueber Admin-Panel verwaltet)
    if db.users_exist():
        ok = db.verify_user(auth.username, auth.password)
        if ok:
            db.touch_login(auth.username)
        return ok
    # 2) Fallback: Env-Zugang (nur solange die DB noch keine Benutzer hat)
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
            logger.warning(
                "401 Unauthorized: %s %s von %s",
                request.method, request.path, request.remote_addr,
            )
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
        logger.warning(
            "401 Unauthorized (API): %s %s von %s",
                request.method, request.path, request.remote_addr,
            )
            return _unauthorized_response()
        return f(*args, **kwargs)

    return wrapper


def _actor():
    auth = request.authorization
    return auth.username if auth else None

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


def available_themes():
    """Alle verfuegbaren Themes = 'default' + jedes Verzeichnis in web/themes mit live.html."""
    themes = ["default"]
    try:
        for p in sorted(THEMES_DIR.iterdir()):
            if p.is_dir() and (p / "live.html").exists():
                themes.append(p.name)
    except Exception:
        pass
    return themes


def get_active_theme():
    theme = db.get_setting("theme", "default")
    return theme if theme in available_themes() else "default"


def resolve_live_page() -> Path:
    theme = get_active_theme()
    if theme != "default":
        candidate = THEMES_DIR / theme / "live.html"
        if candidate.exists():
            return candidate
    return LIVE_PAGE


def serve_live_page():
    page = resolve_live_page()
    resp = make_response(send_file(page, mimetype="text/html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp

# ----------------- Request-Logging -----------------

@app.before_request
def log_http_request():
    logger.info("HTTP %s %s von %s", request.method, request.path, request.remote_addr)


@app.after_request
def log_http_response(response):
    logger.info(
        "HTTP %s %s -> %s", request.method, request.path, response.status_code
    )
    return response

# ----------------- Seiten -----------------

@app.get("/")
def index():
    # Oeffentliche Live-Ansicht inkl. Link zum Admin-Bereich
    return serve_live_page()


@app.get("/live")
def live_preview():
    return serve_live_page()


@app.get("/admin")
@require_auth
def admin_panel():
    logger.info("Admin-Panel geoeffnet von %s (%s)", request.remote_addr, _actor())
    resp = make_response(send_file(ADMIN_PAGE, mimetype="text/html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.get("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory(ASSETS_DIR, filename, max_age=3600)


@app.get("/output/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename, max_age=0)

# ----------------- API: Status & Info -----------------

@app.get("/api/status")
@require_api_key
def api_status():
    return jsonify(
        {"service": "hAI.TPCGCamScript", "status": "running", "version": APP_VERSION}
    )


@app.get("/api/info")
@require_auth
def api_info():
    env_keys = [
        "TZ", "ADMIN_USER", "SFTP_USER", "FTPS_USER", "DATA_ROOT",
        "PUBLIC_BASE_URL", "PROCESS_INTERVAL_SECONDS",
        "OLLAMA_ENABLED", "OLLAMA_BASE_URL", "OLLAMA_MODEL",
    ]
    env = {k: os.getenv(k) for k in env_keys if os.getenv(k) is not None}
    env["API_KEY"] = "gesetzt" if API_KEY else "nicht gesetzt"
    env["ADMIN_PASSWORD"] = (
        "gesetzt (Bootstrap)" if (ADMIN_PASSWORD or ADMIN_PASS_HASH) else "nicht gesetzt"
    )
    return jsonify(
        {
            "service": "hAI.TPCGCamScript",
            "version": APP_VERSION,
            "theme": get_active_theme(),
            "themes_available": available_themes(),
            "ports": {
                "http": {"extern": 8067, "intern": 8080},
                "ftp": {"extern": 21, "intern": 21},
                "ftps": {"extern": 9900, "intern": 990},
                "sftp": {"extern": 2222, "intern": 22},
            },
            "database": {
                "path": str(db.DB_PATH),
                "users": len(db.list_users()),
                "paths": len(db.list_paths()),
                "links": len(db.list_links()),
                "cameras": len(db.list_cameras()),
            },
            "env": env,
        }
    )

# ----------------- API: Theme (DB-persistiert, dynamisch erkannt) -----------------

@app.get("/api/theme")
@require_auth
def get_theme():
    return jsonify({"theme": get_active_theme(), "available": available_themes()})


@app.post("/api/theme")
@require_auth
def set_theme():
    body = request.get_json(silent=True) or {}
    theme = body.get("theme", "default")
    if theme not in available_themes():
        return jsonify(
            {"error": "Unknown theme", "available": available_themes()}
        ), 400
    db.set_setting("theme", theme, actor=_actor())
    write_audit_log("theme_change", {"theme": theme})
    logger.info("Theme geaendert: %s (durch %s)", theme, _actor())
    return jsonify({"theme": theme})

# ----------------- API: Bildpfade (DB) -----------------

@app.get("/api/image-path")
@require_auth
def get_image_path():
    images = {}
    for row in db.list_paths():
        if (OUTPUT_DIR / row["path"]).exists():
            images[row["key"]] = f"/output/{row['path']}"
    if not images:
        return jsonify({"error": "Noch keine Live-Bilder vorhanden"}), 404
    first = next(iter(images.values()))
    return jsonify({"path": first, "images": images})


@app.get("/api/paths")
@require_auth
def api_list_paths():
    return jsonify({"paths": db.list_paths()})


@app.post("/api/paths")
@require_auth
def api_upsert_path():
    body = request.get_json(silent=True) or {}
    key = (body.get("key") or "").strip()
    path = (body.get("path") or "").strip().lstrip("/")
    label = (body.get("label") or "").strip() or key
    if not key or not path or ".." in path:
        return jsonify({"error": "key/path ungueltig"}), 400
    db.upsert_path(key, path, label, actor=_actor())
    logger.info("Pfad gespeichert: %s -> %s (durch %s)", key, path, _actor())
    return jsonify({"status": "saved", "key": key})

# ----------------- API: Links (DB; lesen oeffentlich) -----------------

@app.get("/api/links")
def api_list_links():
    # Oeffentlich lesbar, damit die Live-Seite die Links rendern kann
    return jsonify({"links": db.list_links()})


@app.post("/api/links")
@require_auth
def api_add_link():
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    url = (body.get("url") or "").strip()
    image = (body.get("image") or "").strip()
    if not title or not url.startswith(("http://", "https://")):
        return jsonify({"error": "Titel fehlt oder URL ungueltig"}), 400
    if image and not image.startswith(("http://", "https://", "/")):
        return jsonify({"error": "Bild-URL ungueltig (http(s):// oder /…)"}), 400
    lid = db.add_link(
        title, url, body.get("icon") or "🔗", image, body.get("position") or 0, actor=_actor()
    )
    logger.info("Link angelegt: %s -> %s (durch %s)", title, url, _actor())
    return jsonify({"status": "created", "id": lid})


@app.delete("/api/links/<int:link_id>")
@require_auth
def api_delete_link(link_id):
    ok = db.delete_link(link_id, actor=_actor())
    if not ok:
        return jsonify({"error": "Link nicht gefunden"}), 404
    return jsonify({"status": "deleted", "id": link_id})

# ----------------- API: Kameras (DB) -----------------

@app.get("/api/cameras")
@require_auth
def api_list_cameras():
    return jsonify({"cameras": db.list_cameras()})


@app.post("/api/cameras")
@require_auth
def api_add_camera():
    body = request.get_json(silent=True) or {}
    uid = (body.get("uid") or "").strip()
    name = (body.get("name") or "").strip()
    if not uid or not name:
        return jsonify({"error": "UID und Name sind Pflicht"}), 400
    try:
        cid = db.add_camera(
            uid=uid,
            name=name,
            ip=(body.get("ip") or "").strip(),
            location=(body.get("location") or "").strip(),
            ports=(body.get("ports") or "").strip(),
            active=bool(body.get("active", True)),
            note=(body.get("note") or "").strip(),
            actor=_actor(),
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "Kamera mit dieser UID existiert bereits"}), 409
    logger.info("Kamera angelegt: %s (%s) (durch %s)", name, uid, _actor())
    return jsonify({"status": "created", "id": cid})


@app.post("/api/cameras/<int:cam_id>/active")
@require_auth
def api_toggle_camera(cam_id):
    body = request.get_json(silent=True) or {}
    ok = db.set_camera_active(cam_id, bool(body.get("active")), actor=_actor())
    if not ok:
        return jsonify({"error": "Kamera nicht gefunden"}), 404
    return jsonify({"status": "updated", "id": cam_id, "active": bool(body.get("active"))})


@app.delete("/api/cameras/<int:cam_id>")
@require_auth
def api_delete_camera(cam_id):
    ok = db.delete_camera(cam_id, actor=_actor())
    if not ok:
        return jsonify({"error": "Kamera nicht gefunden"}), 404
    logger.info("Kamera geloescht: id=%s (durch %s)", cam_id, _actor())
    return jsonify({"status": "deleted", "id": cam_id})

# ----------------- API: Benutzer (DB) -----------------

@app.get("/api/users")
@require_auth
def api_list_users():
    return jsonify({"users": db.list_users()})


@app.post("/api/users")
@require_auth
def api_add_user():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    role = body.get("role") or "admin"
    if not username or len(password) < 6:
        return jsonify({"error": "Benutzername fehlt oder Passwort < 6 Zeichen"}), 400
    try:
        uid = db.add_user(username, password, role, actor=_actor())
    except sqlite3.IntegrityError:
        return jsonify({"error": "Benutzer existiert bereits"}), 409
    logger.info("Benutzer angelegt: %s (durch %s)", username, _actor())
    return jsonify({"status": "created", "id": uid})


@app.delete("/api/users/<int:user_id>")
@require_auth
def api_delete_user(user_id):
    ok, msg = db.delete_user(user_id, actor=_actor())
    if not ok:
        return jsonify({"error": msg}), 400
    logger.info("Benutzer geloescht: id=%s (durch %s)", user_id, _actor())
    return jsonify({"status": msg, "id": user_id})

# ----------------- API: Audit (DB) -----------------

@app.get("/api/audit")
@require_auth
def api_audit():
    return jsonify({"entries": db.list_audit(100)})

# ----------------- API: Skripte -----------------

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
    db.add_audit("script_save", {"name": name, "size": len(code)}, actor=_actor())
    logger.info("Skript gespeichert: %s (%d Zeichen)", name, len(code))

    return jsonify({"status": "saved", "name": name})


@app.post("/api/scripts/<name>/run")
@require_auth
def run_script(name):
    path = SCRIPTS_DIR / name
    if not path.exists() or not name.endswith(".py"):
        return jsonify({"error": "Script not found"}), 404

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
        logger.info("Skript ausgefuehrt: %s -> rc=%s", name, result.returncode)
        return jsonify(log_entry)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Script timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/script")
@require_auth
def update_script():
    body = request.get_json(silent=True) or {}
    script_name = body.get("name", "")
    script_code = body.get("code", "")

    if not script_name or not script_code:
        return jsonify({"error": "Invalid request"}), 400

    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return jsonify({"error": "Script not found"}), 404

    script_path.write_text(script_code)
    write_audit_log("script_update", {"name": script_name, "size": len(script_code)})
    db.add_audit("script_update", {"name": script_name}, actor=_actor())
    logger.info("Skript aktualisiert: %s (%d Zeichen)", script_name, len(script_code))
    return jsonify({"status": "Script updated"})

# ----------------- API: Logs -----------------

@app.get("/api/logs")
@require_auth
def get_logs():
    name = request.args.get("file", "app")
    filename = LOG_FILES.get(name)
    if not filename:
        return jsonify(
            {"error": "Unbekannte Log-Datei", "available": sorted(LOG_FILES)}
        ), 404
    log_file = LOGS_DIR / filename
    if not log_file.exists():
        return jsonify({"file": filename, "lines": [], "available": sorted(LOG_FILES)})
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-300:]
    return jsonify({"file": filename, "lines": lines, "available": sorted(LOG_FILES)})


def log_startup():
    logger.info("=" * 50)
    logger.info("hAI.TPCGCamScript v%s - Flask-App initialisiert", APP_VERSION)
    logger.info("DATA_DIR=%s | WEB_DIR=%s", DATA_DIR, WEB_DIR)
    logger.info(
        "SQLite-DB: %s | Benutzer=%d Pfade=%d Links=%d Kameras=%d | Theme=%s",
        db.DB_PATH,
        len(db.list_users()),
        len(db.list_paths()),
        len(db.list_links()),
        len(db.list_cameras()),
        get_active_theme(),
    )
    logger.info("Themes verfuegbar: %s", ", ".join(available_themes()))
    logger.info(
        "Worker-Intervall=%ss | Ollama=%s",
        os.getenv("PROCESS_INTERVAL_SECONDS", "30"),
        os.getenv("OLLAMA_ENABLED", "false"),
    )


log_startup()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
