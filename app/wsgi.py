"""WSGI-Einstieg: bestehende App + Snapshot-Routen."""

from app import main, snapshot

main.LOG_FILES["snapshot"] = "snapshot.log"
snapshot.register(main.app, main.require_auth, main._actor)

app = main.app
