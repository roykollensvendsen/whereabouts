"""The route: every reading the phone sent, kept on this machine for 30 days.

Roy chose 30 days on 2026-10-10, and that saying "slett ruta" wipes it at
once. Nothing here leaves the machine; the file is the person's.
"""

from __future__ import annotations

import itertools
import os
import pathlib
import sqlite3
import threading
import time

from whereabouts.geo import Fix

#: How long a reading is kept.
KEPT_DAYS = 30
#: A silence this long, in seconds, ends one drive; the next reading begins another.
TRIP_PAUSE = 20 * 60
#: A drive shorter than this, in metres, is a walk around the house: not listed.
SHORTEST_TRIP_METRES = 300


def geo_metres(a: Fix, b: Fix) -> float:
    """How far apart two readings are, on the ground, in metres."""
    from whereabouts.geo import metres_between  # noqa: PLC0415 — geo imports Fix from here

    return metres_between(a, b.latitude, b.longitude)


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
        # What the phone last said about itself: its app version and where its sound goes. In memory only.
        self.phone: dict[str, object] = {}
        self.db = sqlite3.connect(str(path) if path else ":memory:", check_same_thread=False)
        if path is not None:
            path.chmod(0o600)
        with self.lock, self.db:
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS readings"
                " (at REAL, latitude REAL, longitude REAL, heading REAL, speed REAL)"
            )
            self.db.execute("CREATE INDEX IF NOT EXISTS readings_at ON readings (at)")
            if "accuracy" not in {row[1] for row in self.db.execute("PRAGMA table_info(readings)")}:
                self.db.execute("ALTER TABLE readings ADD COLUMN accuracy REAL")
            # When Roy began a drive, by pressing "Følg meg".
            self.db.execute("CREATE TABLE IF NOT EXISTS trips (at REAL)")

    def add(self, fix: Fix) -> None:
        """Keep one reading, and let go of any older than KEPT_DAYS."""
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO readings VALUES (?, ?, ?, ?, ?, ?)",
                (fix.at, fix.latitude, fix.longitude, fix.heading, fix.speed, fix.accuracy),
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

    def start_trip(self, at: float | None = None) -> None:
        """Begin a new drive now: the map shows from here on."""
        with self.lock, self.db:
            self.db.execute("INSERT INTO trips VALUES (?)", (time.time() if at is None else at,))
            self.db.execute("DELETE FROM trips WHERE at < ?", (time.time() - KEPT_DAYS * 86400,))

    def trip_began(self) -> float:
        """When the drive now, or the last one, began.

        Roy, 2026-10-10: show only the drive he is on, or old drives clutter
        the map. A drive begins when he presses "Følg meg", or after the
        phone has been silent TRIP_PAUSE, so a forgotten press or an empty
        battery still starts a new one.
        """
        with self.lock:
            (pressed,) = self.db.execute("SELECT COALESCE(MAX(at), 0) FROM trips").fetchone()
            ats = [
                row[0]
                for row in self.db.execute(
                    "SELECT at FROM readings WHERE at >= ? ORDER BY at", (time.time() - KEPT_DAYS * 86400,)
                )
            ]
        began = ats[0] if ats else 0.0
        for before, after in itertools.pairwise(ats):
            # RULE: a silence of TRIP_PAUSE begins a new drive
            if after - before >= TRIP_PAUSE:
                began = after
        return max(float(began), float(pressed))

    def trips(self) -> list[dict[str, float]]:
        """Every drive kept, newest first: when it began and ended, how far and how many readings.

        A drive is cut where Roy pressed "Følg meg" or the phone was silent for
        TRIP_PAUSE; one that hardly moved is left out.
        """
        with self.lock:
            pressed = sorted(row[0] for row in self.db.execute("SELECT at FROM trips"))
        fixes = self.since(time.time() - KEPT_DAYS * 86400)
        drives: list[list[Fix]] = []
        for fix in fixes:
            last = drives[-1][-1] if drives else None
            new = (
                last is None
                or fix.at - last.at >= TRIP_PAUSE
                or any(last.at < at <= fix.at for at in pressed)
            )
            if new:
                drives.append([fix])
            else:
                drives[-1].append(fix)
        listed = []
        for drive in drives:
            metres = sum(geo_metres(a, b) for a, b in itertools.pairwise(drive))
            if len(drive) >= 2 and metres >= SHORTEST_TRIP_METRES:  # noqa: PLR2004 — a line needs two
                listed.append({"began": drive[0].at, "ended": drive[-1].at, "km": round(metres / 1000, 1)})
        return listed[::-1]

    def forget(self) -> int:
        """Wipe the whole route, and say how many readings went."""
        with self.lock, self.db:
            # RULE: "slett ruta" wipes every reading at once
            gone = self.db.execute("DELETE FROM readings").rowcount
        with self.lock:
            self.db.execute("VACUUM")
        return gone


def _fix(row: tuple[float, float, float, float | None, float | None, float | None]) -> Fix:
    at, latitude, longitude, heading, speed, accuracy = row
    return Fix(latitude=latitude, longitude=longitude, heading=heading, speed=speed, at=at, accuracy=accuracy)
