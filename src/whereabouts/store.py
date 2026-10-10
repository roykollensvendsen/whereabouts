"""The route: every reading the phone sent, kept on this machine for 30 days.

Roy chose 30 days on 2026-10-10, and that saying "slett ruta" wipes it at
once. Nothing here leaves the machine; the file is the person's.
"""

from __future__ import annotations

import os
import pathlib
import sqlite3
import threading
import time

from whereabouts.geo import Fix

#: How long a reading is kept.
KEPT_DAYS = 30


def default_path() -> pathlib.Path:
    """Where the route is kept unless told otherwise."""
    base = os.environ.get("XDG_STATE_HOME") or str(pathlib.Path.home() / ".local" / "state")
    return pathlib.Path(base) / "whereabouts" / "route.sqlite"


class Route:
    """The readings, oldest first, in one SQLite file only this user can read."""

    def __init__(self, path: pathlib.Path | None) -> None:
        """Open, or create, the route at `path`; None keeps it in memory."""
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(path) if path else ":memory:", check_same_thread=False)
        if path is not None:
            path.chmod(0o600)
        with self.lock, self.db:
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS readings"
                " (at REAL, latitude REAL, longitude REAL, heading REAL, speed REAL)"
            )
            self.db.execute("CREATE INDEX IF NOT EXISTS readings_at ON readings (at)")

    def add(self, fix: Fix) -> None:
        """Keep one reading, and let go of any older than KEPT_DAYS."""
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO readings VALUES (?, ?, ?, ?, ?)",
                (fix.at, fix.latitude, fix.longitude, fix.heading, fix.speed),
            )
            # RULE: a reading is kept for KEPT_DAYS and no longer
            self.db.execute("DELETE FROM readings WHERE at < ?", (time.time() - KEPT_DAYS * 86400,))

    def latest(self) -> Fix | None:
        """The newest reading, or None when there is none."""
        with self.lock:
            row = self.db.execute("SELECT * FROM readings ORDER BY at DESC LIMIT 1").fetchone()
        return _fix(row) if row else None

    def since(self, at: float) -> list[Fix]:
        """Every reading since `at`, oldest first."""
        with self.lock:
            rows = self.db.execute("SELECT * FROM readings WHERE at >= ? ORDER BY at", (at,)).fetchall()
        return [_fix(row) for row in rows]

    def forget(self) -> int:
        """Wipe the whole route, and say how many readings went."""
        with self.lock, self.db:
            # RULE: "slett ruta" wipes every reading at once
            gone = self.db.execute("DELETE FROM readings").rowcount
        with self.lock:
            self.db.execute("VACUUM")
        return gone


def _fix(row: tuple[float, float, float, float | None, float | None]) -> Fix:
    at, latitude, longitude, heading, speed = row
    return Fix(latitude=latitude, longitude=longitude, heading=heading, speed=speed, at=at)
