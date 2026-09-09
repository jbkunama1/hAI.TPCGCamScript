"""SQLite-Persistenz für hAI.TPCGCamScript.

Speichert Einstellungen (Theme/Frontend-Auswahl), Benutzer, Bildpfade,
Links (inkl. optionalem Bild), Kameras (UID/IP/Name/Einsatzort/Ports/aktiv)
und Admin-Aktionen (Audit) sessions- und container-uebergreifend
in /data/config/tpcg.db (gemountetes Volume).
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
DB_DIR = DATA_DIR / "config"
DB_PATH = DB_DIR / "tpcg.db"

VALID_THEMES = ("default", "original", "modern")

DEFAULT_PATHS = [
    ("tennis", "tennis/webcam_live.jpg", "Tennis"),
    ("padel1", "padel/webcam1_live.jpg", "Padel – Plätze 2+3+4"),
    ("padel2", "padel/webcam2_live.jpg", "Padel – Platz 1 / Center Court"),
]

DEFAULT_LINKS = [
    ("TPC Grötzingen", "https://www.tpc-groetzingen.de", "🎾", 0),
    ("Let's Netz", "https://www.tpcg-lets-netz.de", "🌐", 1),
]


def _now():
    return datetime.utcnow().isoformat() + "Z"


def _connect():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _migrate_links(conn):
    """Aeltere DBs ohne image-Spalte nachtraeglich erweitern."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(links)").fetchall()]
    if cols and "image" not in cols:
        conn.execute("ALTER TABLE links ADD COLUMN image TEXT NOT NULL DEFAULT ''")


def init_db(admin_user="", admin_password="", admin_pass_hash="", legacy_theme_file=None):
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                pass_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin',
                created_at TEXT NOT NULL,
                last_login TEXT
            );
            CREATE TABLE IF NOT EXISTS paths (
                key TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                label TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                icon TEXT NOT NULL DEFAULT '🔗',
                image TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS cameras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                ip TEXT NOT NULL DEFAULT '',
                location TEXT NOT NULL DEFAULT '',
                ports TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                actor TEXT,
                action TEXT NOT NULL,
                details TEXT
            );
            """
        )
        _migrate_links(conn)

        # Theme-Default (mit Migration einer vorhandenen theme.json)
        row = conn.execute("SELECT value FROM settings WHERE key='theme'").fetchone()
        if not row:
            theme = "default"
            if legacy_theme_file is not None:
                try:
                    legacy = json.loads(Path(legacy_theme_file).read_text(encoding="utf-8"))
                    if legacy.get("theme") in VALID_THEMES:
                        theme = legacy["theme"]
                except Exception:
                    pass
            conn.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES ('theme', ?, ?)",
                (theme, _now()),
            )

        # Pfade-Defaults
        if conn.execute("SELECT COUNT(*) c FROM paths").fetchone()["c"] == 0:
            for key, path, label in DEFAULT_PATHS:
                conn.execute(
                    "INSERT INTO paths (key, path, label, updated_at) VALUES (?, ?, ?, ?)",
                    (key, path, label, _now()),
                )

        # Links-Defaults
        if conn.execute("SELECT COUNT(*) c FROM links").fetchone()["c"] == 0:
            for title, url, icon, pos in DEFAULT_LINKS:
                conn.execute(
                    "INSERT INTO links (title, url, icon, position) VALUES (?, ?, ?, ?)",
                    (title, url, icon, pos),
                )

        # Admin-Bootstrap aus Env, solange noch kein Benutzer existiert
        if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
            if admin_pass_hash:
                conn.execute(
                    "INSERT INTO users (username, pass_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
                    (admin_user or "admin", admin_pass_hash, _now()),
                )
            elif admin_password:
                conn.execute(
                    "INSERT INTO users (username, pass_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
                    (admin_user or "admin", generate_password_hash(admin_password), _now()),
                )


# ----------------- Settings -----------------

def get_setting(key, default=None):
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key, value, actor=None):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, str(value), _now()),
        )
    add_audit("setting_change", {"key": key, "value": str(value)}, actor)


# ----------------- Benutzer -----------------

def users_exist():
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] > 0


def verify_user(username, password):
    with _connect() as conn:
        row = conn.execute(
            "SELECT pass_hash FROM users WHERE username=?", (username,)
        ).fetchone()
        if not row:
            return False
        return check_password_hash(row["pass_hash"], password)


def touch_login(username):
    with _connect() as conn:
        conn.execute("UPDATE users SET last_login=? WHERE username=?", (_now(), username))


def list_users():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, username, role, created_at, last_login FROM users ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]


def add_user(username, password, role="admin", actor=None):
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, pass_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(password), role, _now()),
        )
        uid = cur.lastrowid
    add_audit("user_add", {"id": uid, "username": username, "role": role}, actor)
    return uid


def delete_user(user_id, actor=None):
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        if count <= 1:
            return False, "Der letzte Benutzer kann nicht geloescht werden"
        row = conn.execute("SELECT username FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return False, "Benutzer nicht gefunden"
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    add_audit("user_delete", {"id": user_id, "username": row["username"]}, actor)
    return True, "geloescht"


# ----------------- Pfade -----------------

def list_paths():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT key, path, label, updated_at FROM paths ORDER BY key"
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_path(key, path, label, actor=None):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO paths (key, path, label, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET path=excluded.path, label=excluded.label, updated_at=excluded.updated_at",
            (key, path, label, _now()),
        )
    add_audit("path_upsert", {"key": key, "path": path}, actor)


# ----------------- Links -----------------

def list_links():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, url, icon, image, position FROM links ORDER BY position, id"
        ).fetchall()
        return [dict(r) for r in rows]


def add_link(title, url, icon="🔗", image="", position=0, actor=None):
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO links (title, url, icon, image, position) VALUES (?, ?, ?, ?, ?)",
            (title, url, icon or "🔗", image or "", int(position or 0)),
        )
        lid = cur.lastrowid
    add_audit("link_add", {"id": lid, "title": title, "url": url, "image": image}, actor)
    return lid


def delete_link(link_id, actor=None):
    with _connect() as conn:
        row = conn.execute("SELECT title FROM links WHERE id=?", (link_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM links WHERE id=?", (link_id,))
    add_audit("link_delete", {"id": link_id, "title": row["title"]}, actor)
    return True


# ----------------- Kameras -----------------

def list_cameras():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, uid, name, ip, location, ports, active, note, created_at FROM cameras ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]


def add_camera(uid, name, ip="", location="", ports="", active=True, note="", actor=None):
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO cameras (uid, name, ip, location, ports, active, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, name, ip, location, ports, 1 if active else 0, note, _now()),
        )
        cid = cur.lastrowid
    add_audit("camera_add", {"id": cid, "uid": uid, "name": name}, actor)
    return cid


def set_camera_active(cam_id, active, actor=None):
    with _connect() as conn:
        row = conn.execute("SELECT name FROM cameras WHERE id=?", (cam_id,)).fetchone()
        if not row:
            return False
        conn.execute("UPDATE cameras SET active=? WHERE id=?", (1 if active else 0, cam_id))
    add_audit("camera_active", {"id": cam_id, "active": bool(active)}, actor)
    return True


def delete_camera(cam_id, actor=None):
    with _connect() as conn:
        row = conn.execute("SELECT name FROM cameras WHERE id=?", (cam_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM cameras WHERE id=?", (cam_id,))
    add_audit("camera_delete", {"id": cam_id, "name": row["name"]}, actor)
    return True


# ----------------- Audit -----------------

def add_audit(action, details=None, actor=None):
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO audit (ts, actor, action, details) VALUES (?, ?, ?, ?)",
                (_now(), actor, action, json.dumps(details or {}, ensure_ascii=False)),
            )
    except Exception:
        pass


def list_audit(limit=100):
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, ts, actor, action, details FROM audit ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(r) for r in rows]
