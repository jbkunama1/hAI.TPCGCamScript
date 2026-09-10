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

APP_VERSION = os.getenv("APP_VERSION", "1.5.0")
app = Flask(__name__)
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH", "")
API_KEY = os.getenv("API_KEY", "")
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
for d in [INPUT_DIR, OUTPUT_DIR, SCRIPTS_DIR, BACKUPS_DIR, LOGS_DIR, CONFIG_DIR]:
    d.mkdir(parents=True, exist_ok=True)
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
LOG_FILES = {
    "app": "app.log",
    "server": "server.log",
    "worker": "worker.log",
    "worker-errors": "worker-errors.log",
    "sshd": "sshd.log",
    "gunicorn-access": "gunicorn-access.log",
}
DEFAULT_SINGLE = """from pathlib import Path
from PIL import Image
INPUT_DIR = Path('/data/input')
OUTPUT_DIR = Path('/data/output')
def process():
    files = list(INPUT_DIR.rglob('*.jpg')) + list(INPUT_DIR.rglob('*.png'))
    if not files:
        return
    src = max(files, key=lambda p: p.stat().st_mtime)
    img = Image.open(src)
    w, h = img.size
    size = min(w, h)
    cropped = img.crop(((w-size)//2, (h-size)//2, (w+size)//2, (h+size)//2)).resize((512, 512))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cropped.save(OUTPUT_DIR / 'eingang.jpg', quality=85)
if __name__ == '__main__':
    process()
"""
DEFAULT_PAIR = """from pathlib import Path
from PIL import Image
INPUT_DIR = Path('/data/input')
OUTPUT_DIR = Path('/data/output')
def process():
    files = sorted(list(INPUT_DIR.rglob('*.jpg')) + list(INPUT_DIR.rglob('*.png')), key=lambda p: p.stat().st_mtime, reverse=True)[:2]
    if len(files) < 2:
        return
    images = [Image.open(p).convert('RGB').resize((512,512)) for p in files]
    combined = Image.new('RGB', (1024,512))
    combined.paste(images[0], (0,0)); combined.paste(images[1], (512,0))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined.save(OUTPUT_DIR / 'lounge-centercourt.jpg', quality=85)
if __name__ == '__main__':
    process()
"""
if not (SCRIPTS_DIR / 'process_single.py').exists():
    (SCRIPTS_DIR / 'process_single.py').write_text(DEFAULT_SINGLE)
if not (SCRIPTS_DIR / 'process_pair.py').exists():
    (SCRIPTS_DIR / 'process_pair.py').write_text(DEFAULT_PAIR)
db.init_db(ADMIN_USER, ADMIN_PASSWORD, ADMIN_PASS_HASH, LEGACY_THEME_FILE)
def _unauthorized_response():
    resp = make_response(jsonify({'error':'Unauthorized'}), 401)
    resp.headers['WWW-Authenticate'] = 'Basic realm="TPCG Admin"'
    return resp
def check_basic_auth():
    auth = request.authorization
    if not auth or auth.type != 'basic':
        return False
    if db.users_exist():
        ok = db.verify_user(auth.username, auth.password)
        if ok:
            db.touch_login(auth.username)
        return ok
    if auth.username != ADMIN_USER:
        return False
    return check_password_hash(ADMIN_PASS_HASH, auth.password) if ADMIN_PASS_HASH else auth.password == ADMIN_PASSWORD
def require_auth(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs) if check_basic_auth() else _unauthorized_response()
    return wrapper
def require_api_key(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs) if request.headers.get('X-API-Key','') == API_KEY or check_basic_auth() else _unauthorized_response()
    return wrapper
def _actor():
    auth = request.authorization
    return auth.username if auth else None
_SECRET_MARKERS = ('PASSWORD','PASS','SECRET','TOKEN','API_KEY','HASH','PRIVATE')
def masked_env():
    return {k: ('********' if v else '(leer)') if any(m in k.upper() for m in _SECRET_MARKERS) else (v or '') for k,v in sorted(os.environ.items())}
def write_audit_log(action, details):
    with (LOGS_DIR/'audit.jsonl').open('a') as f:
        f.write(json.dumps({'timestamp':datetime.utcnow().isoformat()+'Z','action':action,'details':details})+'\n')
def backup_script(path):
    if path.exists():
        path_out = BACKUPS_DIR / f'{path.stem}-{datetime.utcnow().strftime("%Y%m%d-%H%M%S")}{path.suffix}'
        path_out.write_bytes(path.read_bytes())
def validate_python_code(code):
    import tempfile
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as f:
        f.write(code); tmp = f.name
    try:
        r = subprocess.run([sys.executable,'-m','py_compile',tmp],capture_output=True,text=True)
        return (r.returncode == 0, r.stderr)
    finally:
        Path(tmp).unlink(missing_ok=True)
def available_themes():
    themes=['default']
    try:
        themes += [p.name for p in sorted(THEMES_DIR.iterdir()) if p.is_dir() and (p/'live.html').exists()]
    except Exception:
        pass
    return themes
def get_active_theme():
    theme=db.get_setting('theme','default')
    return theme if theme in available_themes() else 'default'
def serve_live_page():
    page=LIVE_PAGE
    theme=get_active_theme()
    if theme != 'default' and (THEMES_DIR/theme/'live.html').exists():
        page=THEMES_DIR/theme/'live.html'
    resp=make_response(send_file(page,mimetype='text/html'))
    resp.headers['Cache-Control']='no-cache, no-store, must-revalidate'
    return resp
@app.before_request
def log_http_request():
    logger.info('HTTP %s %s von %s',request.method,request.path,request.remote_addr)
@app.after_request
def log_http_response(response):
    logger.info('HTTP %s %s -> %s',request.method,request.path,response.status_code)
    return response
@app.get('/')
def index(): return serve_live_page()
@app.get('/live')
def live_preview(): return serve_live_page()
@app.get('/admin')
@require_auth
def admin_panel(): return send_file(ADMIN_PAGE,mimetype='text/html')
@app.get('/assets/<path:filename>')
def serve_assets(filename): return send_from_directory(ASSETS_DIR,filename,max_age=3600)
@app.get('/output/<path:filename>')
def serve_output(filename): return send_from_directory(OUTPUT_DIR,filename,max_age=0)
@app.get('/api/status')
@require_api_key
def api_status(): return jsonify({'service':'hAI.TPCGCamScript','status':'running','version':APP_VERSION})
@app.get('/api/info')
@require_auth
def api_info():
    return jsonify({'service':'hAI.TPCGCamScript','version':APP_VERSION,'theme':get_active_theme(),'themes_available':available_themes(),'ports':{'http':{'extern':8067,'intern':8080},'ftp':'separater hai-transfer-Container','ftps':'separater hai-transfer-Container','sftp':'separater hai-transfer-Container'},'database':{'path':str(db.DB_PATH),'users':len(db.list_users()),'paths':len(db.list_paths()),'links':len(db.list_links()),'cameras':len(db.list_cameras())},'env':masked_env()})
@app.get('/api/theme')
@require_auth
def get_theme(): return jsonify({'theme':get_active_theme(),'available':available_themes()})
@app.post('/api/theme')
@require_auth
def set_theme():
    body=request.get_json(silent=True) or {}; theme=body.get('theme','default')
    if theme not in available_themes(): return jsonify({'error':'Unknown theme','available':available_themes()}),400
    db.set_setting('theme',theme,actor=_actor()); write_audit_log('theme_change',{'theme':theme}); return jsonify({'theme':theme})
@app.get('/api/image-path')
@require_auth
def get_image_path():
    images={row['key']:f"/output/{row['path']}" for row in db.list_paths() if (OUTPUT_DIR/row['path']).exists()}
    return jsonify({'path':next(iter(images.values())),'images':images}) if images else (jsonify({'error':'Noch keine Live-Bilder vorhanden'}),404)
@app.get('/api/paths')
@require_auth
def api_list_paths(): return jsonify({'paths':db.list_paths()})
@app.post('/api/paths')
@require_auth
def api_upsert_path():
    body=request.get_json(silent=True) or {}; key=(body.get('key') or '').strip(); path=(body.get('path') or '').strip().lstrip('/'); label=(body.get('label') or '').strip() or key
    if not key or not path or '..' in path: return jsonify({'error':'key/path ungueltig'}),400
    db.upsert_path(key,path,label,actor=_actor()); return jsonify({'status':'saved','key':key})
@app.get('/api/links')
def api_list_links(): return jsonify({'links':db.list_links()})
@app.post('/api/links')
@require_auth
def api_add_link():
    body=request.get_json(silent=True) or {}; title=(body.get('title') or '').strip(); url=(body.get('url') or '').strip(); image=(body.get('image') or '').strip()
    if not title or not url.startswith(('http://','https://')): return jsonify({'error':'Titel fehlt oder URL ungueltig'}),400
    if image and not image.startswith(('http://','https://','/')): return jsonify({'error':'Bild-URL ungueltig'}),400
    return jsonify({'status':'created','id':db.add_link(title,url,body.get('icon') or '🔗',image,body.get('position') or 0,actor=_actor())})
@app.delete('/api/links/<int:link_id>')
@require_auth
def api_delete_link(link_id): return jsonify({'status':'deleted','id':link_id}) if db.delete_link(link_id,actor=_actor()) else (jsonify({'error':'Link nicht gefunden'}),404)
@app.get('/api/cameras')
@require_auth
def api_list_cameras(): return jsonify({'cameras':db.list_cameras()})
@app.post('/api/cameras')
@require_auth
def api_add_camera():
    body=request.get_json(silent=True) or {}; uid=(body.get('uid') or '').strip(); name=(body.get('name') or '').strip()
    if not uid or not name: return jsonify({'error':'UID und Name sind Pflicht'}),400
    try: cid=db.add_camera(uid,name,(body.get('ip') or '').strip(),(body.get('location') or '').strip(),(body.get('ports') or '').strip(),bool(body.get('active',True)),(body.get('note') or '').strip(),actor=_actor())
    except sqlite3.IntegrityError: return jsonify({'error':'Kamera mit dieser UID existiert bereits'}),409
    return jsonify({'status':'created','id':cid})
@app.post('/api/cameras/<int:cam_id>/active')
@require_auth
def api_toggle_camera(cam_id):
    body=request.get_json(silent=True) or {}; return jsonify({'status':'updated','id':cam_id,'active':bool(body.get('active'))}) if db.set_camera_active(cam_id,bool(body.get('active')),actor=_actor()) else (jsonify({'error':'Kamera nicht gefunden'}),404)
@app.delete('/api/cameras/<int:cam_id>')
@require_auth
def api_delete_camera(cam_id): return jsonify({'status':'deleted','id':cam_id}) if db.delete_camera(cam_id,actor=_actor()) else (jsonify({'error':'Kamera nicht gefunden'}),404)
@app.get('/api/users')
@require_auth
def api_list_users(): return jsonify({'users':db.list_users()})
@app.post('/api/users')
@require_auth
def api_add_user():
    body=request.get_json(silent=True) or {}; username=(body.get('username') or '').strip(); password=body.get('password') or ''; role=body.get('role') or 'admin'
    if not username or len(password)<6: return jsonify({'error':'Benutzername fehlt oder Passwort < 6 Zeichen'}),400
    try: uid=db.add_user(username,password,role,actor=_actor())
    except sqlite3.IntegrityError: return jsonify({'error':'Benutzer existiert bereits'}),409
    return jsonify({'status':'created','id':uid})
@app.delete('/api/users/<int:user_id>')
@require_auth
def api_delete_user(user_id):
    ok,msg=db.delete_user(user_id,actor=_actor()); return jsonify({'status':msg,'id':user_id}) if ok else (jsonify({'error':msg}),400)
@app.get('/api/audit')
@require_auth
def api_audit(): return jsonify({'entries':db.list_audit(100)})
@app.get('/api/scripts')
@require_auth
def list_scripts(): return jsonify({'scripts':[{'name':p.name,'size':p.stat().st_size,'modified':datetime.utcfromtimestamp(p.stat().st_mtime).isoformat()+'Z'} for p in SCRIPTS_DIR.glob('*.py')]})
@app.get('/api/scripts/<name>')
@require_auth
def get_script(name):
    path=SCRIPTS_DIR/name
    return jsonify({'name':name,'code':path.read_text()}) if path.exists() and name.endswith('.py') else (jsonify({'error':'Script not found'}),404)
@app.post('/api/scripts/<name>')
@require_auth
def save_script(name):
    path=SCRIPTS_DIR/name; body=request.get_json(silent=True) or {}; code=body.get('code','')
    if not name.endswith('.py'): return jsonify({'error':'Invalid filename'}),400
    ok,err=validate_python_code(code)
    if not ok: return jsonify({'error':'Invalid Python code','details':err}),400
    backup_script(path); path.write_text(code); write_audit_log('script_save',{'name':name,'size':len(code)}); db.add_audit('script_save',{'name':name,'size':len(code)},actor=_actor()); return jsonify({'status':'saved','name':name})
@app.post('/api/scripts/<name>/run')
@require_auth
def run_script(name):
    path=SCRIPTS_DIR/name
    if not path.exists() or not name.endswith('.py'): return jsonify({'error':'Script not found'}),404
    try:
        r=subprocess.run([sys.executable,str(path)],capture_output=True,text=True,timeout=30); entry={'script':name,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}; (LOGS_DIR/'script_runs.jsonl').open('a').write(json.dumps(entry)+'\n'); return jsonify(entry)
    except subprocess.TimeoutExpired: return jsonify({'error':'Script timed out'}),504
    except Exception as e: return jsonify({'error':str(e)}),500
@app.get('/api/logs')
@require_auth
def get_logs():
    name=request.args.get('file','app'); filename=LOG_FILES.get(name)
    if not filename: return jsonify({'error':'Unbekannte Log-Datei','available':sorted(LOG_FILES)}),404
    path=LOGS_DIR/filename
    return jsonify({'file':filename,'lines':path.read_text(encoding='utf-8',errors='replace').splitlines()[-300:] if path.exists() else [],'available':sorted(LOG_FILES)})
logger.info('hAI.TPCGCamScript v%s - Transfer-Stack ausgelagert',APP_VERSION)
if __name__ == '__main__': app.run(host='0.0.0.0',port=8080)
