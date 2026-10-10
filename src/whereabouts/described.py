"""Places Hermes has described, kept so the phone tells of them every time Roy passes.

Roy, 2026-10-10: Hermes writes what is said about each place himself, and what
he has written is kept, so the same places are told of the next time Roy drives
past, and there are more of them along the roads he drives as time goes on. The
phone fetches the places near Roy and decides on its own, reading by reading,
when one is close enough to speak.
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Any

from whereabouts import geo
from whereabouts.store import KEPT_DAYS

if TYPE_CHECKING:
    from whereabouts.store import Route

#: How close, in metres, a place counts as passed unless Hermes says otherwise.
DEFAULT_RADIUS_M = 150
#: Below this, a car at speed would pass between two readings without noticing.
SMALLEST_RADIUS_M = 30
#: Above this, a place would be told long before anything can be seen.
LARGEST_RADIUS_M = 3000
#: The most places one call describes.
MAX_PLACES = 200
#: The longest text told at one place, in characters: about half a minute.
LONGEST_SAID = 600
#: Two descriptions of a place by the same name this close are the same place.
SAME_NAME_METRES = 500
#: Two descriptions this close are the same place, whatever they are called.
SAME_SPOT_METRES = 25
#: What Hermes wrote about a place.
PLACE = "place"
#: What Roy said to leave by the road, for himself the next time he passes.
NOTE = "note"
#: Fresh local news about a place, told until it fades.
NEWS = "news"
#: How long news is told, in days, unless Hermes says otherwise; and the longest.
NEWS_DAYS = 7
LONGEST_NEWS_DAYS = 30


class Places:
    """Every place described, kept in the route's own file until forgotten."""

    def __init__(self, route: Route) -> None:
        """Keep places beside `route`'s readings."""
        self.lock = route.lock
        self.db = route.db
        with self.lock, self.db:
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS described (id INTEGER PRIMARY KEY, name TEXT, latitude REAL,"
                " longitude REAL, radius_m INTEGER, said TEXT, written REAL, kind TEXT DEFAULT 'place')"
            )
            self.db.execute("CREATE INDEX IF NOT EXISTS described_at ON described (latitude, longitude)")
            # What was told, and when: for going through a drive afterwards. No position is kept here.
            self.db.execute("CREATE TABLE IF NOT EXISTS told (at REAL, place INTEGER, name TEXT, said TEXT)")
            columns = {row[1] for row in self.db.execute("PRAGMA table_info(described)")}
            if "until" not in columns:  # kept before news could fade
                self.db.execute("ALTER TABLE described ADD COLUMN until REAL")

    def add(
        self, places: list[dict[str, Any]], kind: str = PLACE, until: float | None = None
    ) -> dict[str, int]:
        """Keep each place, updating one already described rather than adding it twice."""
        # RULE: one call describes at most MAX_PLACES
        if len(places) > MAX_PLACES:
            msg = f"Høyst {MAX_PLACES} steder om gangen."
            raise ValueError(msg)
        checked = [_place(place) for place in places]
        added = updated = 0
        for place in checked:
            same = self._same(place, kind)
            with self.lock, self.db:
                # RULE: a place described again is updated, not added twice
                if same is not None:
                    self.db.execute(
                        "UPDATE described SET name=?, latitude=?, longitude=?, radius_m=?, said=?, written=?,"
                        " until=? "
                        "WHERE id=?",
                        (*_row(place), time.time(), until, same),
                    )
                    updated += 1
                else:
                    self.db.execute(
                        "INSERT INTO described"
                        " (name, latitude, longitude, radius_m, said, written, kind, until)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (*_row(place), time.time(), kind, until),
                    )
                    added += 1
        with self.lock, self.db:
            self.db.execute("DELETE FROM described WHERE until IS NOT NULL AND until < ?", (time.time(),))
        return {"added": added, "updated": updated}

    def near(self, latitude: float, longitude: float, metres: float) -> list[dict[str, Any]]:
        """Every place described within `metres` of a point, nearest first."""
        dlat = metres / 111_320
        dlon = metres / (111_320 * max(math.cos(math.radians(latitude)), 0.01))
        with self.lock:
            rows = self.db.execute(
                "SELECT id, name, latitude, longitude, radius_m, said, kind FROM described"
                " WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?"
                # RULE: news is told only until it fades
                " AND (until IS NULL OR until > ?)",
                (latitude - dlat, latitude + dlat, longitude - dlon, longitude + dlon, time.time()),
            ).fetchall()
        here = geo.Fix(latitude, longitude, None, None, 0.0)
        found = []
        for row in rows:
            distance = geo.metres_between(here, row[2], row[3])
            if distance <= metres:
                keys = ("id", "name", "latitude", "longitude", "radius_m", "said", "kind")
                found.append((distance, dict(zip(keys, row, strict=True))))
        return [place for _, place in sorted(found, key=lambda pair: pair[0])]

    def get(self, place_id: int) -> dict[str, Any] | None:
        """One place by its id, or None when it is gone."""
        with self.lock:
            row = self.db.execute(
                "SELECT id, name, latitude, longitude, radius_m, said, kind FROM described WHERE id = ?",
                (place_id,),
            ).fetchone()
        keys = ("id", "name", "latitude", "longitude", "radius_m", "said", "kind")
        return dict(zip(keys, row, strict=True)) if row else None

    def mark_told(self, place_id: int) -> None:
        """Note that the phone told of this place now; forget notes older than KEPT_DAYS."""
        place = self.get(place_id)
        if place is None:
            return
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO told VALUES (?, ?, ?, ?)", (time.time(), place_id, place["name"], place["said"])
            )
            # RULE: what was told is kept as long as the route, and no longer
            self.db.execute("DELETE FROM told WHERE at < ?", (time.time() - KEPT_DAYS * 86400,))

    def told_since(self, at: float) -> list[dict[str, Any]]:
        """What the phone told of since `at`, oldest first: when, which place, and what was said."""
        with self.lock:
            rows = self.db.execute(
                "SELECT at, place, name, said FROM told WHERE at >= ? ORDER BY at", (at,)
            ).fetchall()
        return [
            {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(a)), "id": p, "name": n, "said": s}
            for a, p, n, s in rows
        ]

    def version(self) -> str:
        """Changes whenever a place is added, changed or forgotten, so the phone knows to fetch again."""
        with self.lock:
            count, written = self.db.execute("SELECT COUNT(*), MAX(written) FROM described").fetchone()
        return f"{count}-{written or 0:.3f}"

    def forget(self, name: str) -> int:
        """Forget every place by this name, and every note holding these words; say how many went."""
        wanted = name.strip()
        if not wanted:
            return 0
        with self.lock, self.db:
            # A note can be forgotten by a few of its words: "glem meldingen om ved".
            return self.db.execute(
                "DELETE FROM described"
                " WHERE lower(name) = lower(?) OR (kind = ? AND lower(said) LIKE lower(?))",
                (wanted, NOTE, f"%{wanted}%"),
            ).rowcount

    def _same(self, place: dict[str, Any], kind: str) -> int | None:
        # RULE: a note is never merged with a place or another note
        if kind == NOTE:
            return None
        for near in self.near(place["latitude"], place["longitude"], SAME_NAME_METRES):
            if near["kind"] != kind:
                continue
            here = geo.Fix(place["latitude"], place["longitude"], None, None, 0.0)
            close = geo.metres_between(here, near["latitude"], near["longitude"])
            if close <= SAME_SPOT_METRES or (
                place["name"] and near["name"].casefold() == place["name"].casefold()
            ):
                return int(near["id"])
        return None


def _row(place: dict[str, Any]) -> tuple[Any, ...]:
    return (place["name"], place["latitude"], place["longitude"], place["radius_m"], place["said"])


def _place(place: dict[str, Any]) -> dict[str, Any]:
    """One place, checked: where, how close counts, and what is told there."""
    try:
        latitude, longitude = float(place["latitude"]), float(place["longitude"])
    except (KeyError, TypeError, ValueError):
        msg = "Hvert sted trenger latitude og longitude."
        raise ValueError(msg) from None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):  # noqa: PLR2004 — the globe's edges
        msg = "latitude eller longitude er utenfor kloden."
        raise ValueError(msg)
    said = str(place.get("said") or "").strip()
    if not said:
        msg = "Hvert sted trenger said: det som leses opp."
        raise ValueError(msg)
    radius = float(place.get("radius_m") or DEFAULT_RADIUS_M)
    return {
        "name": str(place.get("name") or "").strip(),
        "latitude": round(latitude, 6),
        "longitude": round(longitude, 6),
        # RULE: a place's radius is kept within what a car can use
        "radius_m": round(min(max(radius, SMALLEST_RADIUS_M), LARGEST_RADIUS_M)),
        "said": said[:LONGEST_SAID],
    }
