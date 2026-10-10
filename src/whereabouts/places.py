"""The name of the place a reading is in, looked up again only after a real move.

Nominatim, OpenStreetMap's name service, asks for no more than one lookup a
second. A phone sends a reading every few seconds, so a name is kept until the
person has moved RENAME_METRES.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

from whereabouts import geo

if TYPE_CHECKING:
    from collections.abc import Callable

    #: Anything that names a reading.
    Namer = Callable[[geo.Fix], str | None]

PLACES_URL = "https://nominatim.openstreetmap.org/reverse"
PLACES_SECONDS = 8.0
#: How far the person must move before the name is looked up again.
RENAME_METRES = 150


def place_of(latitude: float, longitude: float) -> str | None:
    """The name of a place, down to the street, from coordinates nobody can say out loud."""
    query = urllib.parse.urlencode({"lat": latitude, "lon": longitude, "format": "jsonv2", "zoom": 18})
    request = urllib.request.Request(  # noqa: S310 — a constant HTTPS URL
        f"{PLACES_URL}?{query}", headers={"User-Agent": geo.POLITE}
    )
    try:
        with urllib.request.urlopen(request, timeout=PLACES_SECONDS) as reply:  # noqa: S310 — as above
            found = json.loads(reply.read() or b"{}").get("address") or {}
    except (OSError, json.JSONDecodeError):
        return None
    near = found.get("city") or found.get("town") or found.get("village") or found.get("municipality")
    street = " ".join(part for part in (found.get("road"), found.get("house_number")) if part)
    small = found.get("suburb") or found.get("hamlet") or found.get("neighbourhood")
    return ", ".join(part for part in (street, small, near) if part) or None


class Names:
    """Names readings, asking again only after a move of RENAME_METRES."""

    def __init__(self, lookup: Callable[[float, float], str | None] | None = None) -> None:
        """Name with `lookup`, Nominatim unless told otherwise."""
        self.lookup = lookup or place_of
        self.last: tuple[geo.Fix, str] | None = None

    def __call__(self, fix: geo.Fix) -> str | None:
        """The name of the place `fix` is in."""
        if self.last and geo.metres_between(self.last[0], fix.latitude, fix.longitude) < RENAME_METRES:
            return self.last[1]
        name = self.lookup(fix.latitude, fix.longitude)
        if name:
            self.last = (fix, name)
        return name
