"""WSGI-Einstieg: bestehende App + Snapshot-Routen + Umgebungs-Ansicht."""

import os

from flask import jsonify, request

from app import db, main, snapshot

main.LOG_FILES["snapshot"] = "snapshot.log"
snapshot.register(main.app, main.require_auth, main._actor)

ENV_GROUPS = [
    ("Auth & API", ("ADMIN_", "API_KEY")),
    ("FTP/SSH-Variablen", ("PASV_", "FTP", "SFTP", "SSH", "TRANSFER_")),
    ("App & Worker", ("APP_", "DATA_", "TZ", "WORKER_", "LOG_", "PROCESS_", "OLLAMA", "DB_", "PUBLIC_")),
]
ENV_ORDER = ["FTP-Zugang", "Auth & API", "FTP/SSH-Variablen", "App & Worker", "System"]
FTP_USER_VARS = ("FTP_USER", "FTP_USERNAME", "FTPUSER", "TRANSFER_USER")
FTP_PASS_VARS = ("FTP_PASS", "FTP_PASSWORD", "FTPPASS", "TRANSFER_PASSWORD")


def _env_group(key):
    up = key.upper()
    for name, prefixes in ENV_GROUPS:
        if up.startswith(prefixes):
            return name
    return "System"


def _first_set(names):
    for n in names:
        v = os.getenv(n, "")
        if v:
            return n, v
    return None, ""


def _ftp_info():
    host = os.getenv("PASV_ADDRESS", "")
    u_src, u_val = _first_set(FTP_USER_VARS)
    p_src, _ = _first_set(FTP_PASS_VARS)
    user = (u_val + " (aus " + u_src + ")") if u_src else "ftpuser (Standard - FTP_USER nicht gesetzt)"
    pw = ("gesetzt (aus " + p_src + ")") if p_src else "STANDARD 'password' - FTP_PASS nicht gesetzt!"
    rows = [
        ("Host (PASV_ADDRESS)", host or "NICHT GESETZT - Passiv-Modus von aussen gestoert"),
        ("Benutzer", user),
        ("Passwort", pw),
        ("FTP / explizites FTPS", "extern 21 -> intern 21"),
        ("Implizites FTPS", "extern 9900 -> intern 990"),
        ("SFTP", "extern 2222 -> intern 22"),
        ("Passive Ports", "30000-30010 (21: 30000-30005, 990: 30006-30010)"),
    ]
    return [{"key": k, "value": v, "secret": False} for k, v in rows]


@main.app.get("/api/env")
@main.require_auth
def api_env():
    reveal = request.args.get("reveal") == "1"
    if reveal:
        db.add_audit("env_reveal", {}, main._actor())
    groups = {"FTP-Zugang": _ftp_info()}
    for key, value in sorted(os.environ.items()):
        secret = any(m in key.upper() for m in main._SECRET_MARKERS)
        shown = value if (reveal or not secret) else ("********" if value else "(leer)")
        groups.setdefault(_env_group(key), []).append({"key": key, "value": shown, "secret": secret})
    return jsonify({"groups": groups, "order": ENV_ORDER, "revealed": reveal})


app = main.app
