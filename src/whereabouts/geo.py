"""Readings, directions and what is around them: the arithmetic, and OpenStreetMap.

Begun in voice-integration as `voice_bridge.moving`, and moved here when where
Roy is became a service of its own.
"""

from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    #: Anything that runs an Overpass query and returns what it found.
    Fetch = Callable[[str], dict[str, Any]]

#: Where named things near a point are asked for.
NEARBY_URL = "https://overpass-api.de/api/interpreter"
NEARBY_SECONDS = 8.0
#: How far around the person to look, in metres.
NEARBY_METRES = 400
POLITE = "voice-integration (github.com/roykollensvendsen/voice-integration)"
#: Below this the direction a phone reports is noise: standing still, it points anywhere.
MOVING_METRES_PER_SECOND = 1.5
#: A reading older than this is not "where you are now".
FRESH_SECONDS = 120.0
#: How wide each side is, either way of its centre line, in degrees.
SIDE_WIDTH = 60.0

#: Each side, as degrees from the direction of travel.
SIDES = {"venstre": -90.0, "høyre": 90.0, "foran": 0.0, "bak": 180.0}
_SIDE = re.compile(
    r"\b(?:hva|hvem|hvilken|hvilket)\b.{0,40}?\b(?:til|på)\s+(venstre|høyre)\b"
    r"|\b(?:hva|hvilken|hvilket)\b.{0,40}?\b(foran|bak)\s+(?:oss|meg)\b"
    r"|\bwhat\b.{0,40}?\bon\s+(?:the|my|our)\s+(left|right)\b"
)
_ENGLISH = {"left": "venstre", "right": "høyre"}
_COMPASS = ("nord", "nordøst", "øst", "sørøst", "sør", "sørvest", "vest", "nordvest")
#: What a thing is, when its kind can be said in Norwegian.
_KIND = {
    "church": "kirke",
    "place_of_worship": "kirke",
    "school": "skole",
    "fuel": "bensinstasjon",
    "restaurant": "restaurant",
    "cafe": "kafé",
    "supermarket": "butikk",
    "museum": "museum",
    "viewpoint": "utsiktspunkt",
    "attraction": "severdighet",
    "hotel": "hotell",
    "park": "park",
    "peak": "fjelltopp",
    "bay": "bukt",
    "island": "øy",
    "islet": "holme",
    "lighthouse": "fyr",
    "monument": "minnesmerke",
    "memorial": "minnesmerke",
    "ruins": "ruin",
    "castle": "festning",
    "farm": "gård",
    "hamlet": "grend",
    "village": "bygd",
    "locality": "sted",
}


@dataclass(frozen=True)
class Fix:
    """One reading from the phone: where, which way, how fast, and when."""

    latitude: float
    longitude: float
    heading: float | None = None
    speed: float | None = None
    at: float = 0.0

    def moving(self) -> bool:
        """Whether the direction means anything: the phone is going somewhere."""
        return self.heading is not None and (self.speed or 0.0) >= MOVING_METRES_PER_SECOND

    def fresh(self, now: float | None = None) -> bool:
        """Whether this is still where the person is."""
        return (time.time() if now is None else now) - self.at <= FRESH_SECONDS


def fix_from(body: dict[str, Any], now: float | None = None) -> Fix:
    """A reading from what the page sent: heading and speed only when the phone gave them."""

    def number(key: str) -> float | None:
        value = body.get(key)
        return float(value) if isinstance(value, (int, float)) and not math.isnan(value) else None

    return Fix(
        latitude=float(body.get("latitude", 0)),
        longitude=float(body.get("longitude", 0)),
        heading=number("heading"),
        speed=number("speed"),
        at=_when(body.get("at"), time.time() if now is None else now),
    )


#: How far a reading's own time may be from the clock before it is not believed.
TRUSTED_SKEW_SECONDS = 3600.0


def _when(said: object, now: float) -> float:
    """When the phone measured, if it said so believably; when it arrived, otherwise."""
    if isinstance(said, (int, float)) and not math.isnan(said) and abs(now - said) <= TRUSTED_SKEW_SECONDS:
        return float(said)
    return now


def metres_between(a: Fix, latitude: float, longitude: float) -> float:
    """How far a point is from a reading, on the ground."""
    north = math.radians(latitude - a.latitude) * 6_371_000
    east = math.radians(longitude - a.longitude) * 6_371_000 * math.cos(math.radians(a.latitude))
    return math.hypot(north, east)


def bearing_to(a: Fix, latitude: float, longitude: float) -> float:
    """Which way a point lies from a reading, in degrees from north."""
    north = latitude - a.latitude
    east = (longitude - a.longitude) * math.cos(math.radians(a.latitude))
    return math.degrees(math.atan2(east, north)) % 360


def compass(heading: float) -> str:
    """A direction a person says: "nordøst", not 47 degrees."""
    return _COMPASS[round(heading / 45) % 8]


def described(fix: Fix | None, place: str | None, *, timed: bool = False) -> str:
    """Where the person is, and which way and how fast they are going, in one sentence.

    `timed` adds when the phone said so: Hermes reads it, and a reading is only
    worth what its age allows. Roy, 2026-10-10.
    """
    if not place:
        return "Jeg vet ikke hvor du er."
    when = f" Målt klokka {time.strftime('%H:%M:%S', time.localtime(fix.at))}." if timed and fix else ""
    if fix is None or not fix.moving():
        return f"Du er i {place}, og står stille.{when}" if timed and fix else f"Du er i {place}."
    km_h = round((fix.speed or 0.0) * 3.6 / 5) * 5
    going = f"på vei {compass(fix.heading or 0.0)} i omtrent {km_h} kilometer i timen"
    return f"Du er i {place}, {going}.{when}"


def side_asked(said: str) -> str | None:
    """Which side "hva er det til venstre for oss" asks about, or None."""
    found = _SIDE.search(" ".join(said.casefold().split()))
    if not found:
        return None
    side = next(group for group in found.groups() if group)
    return _ENGLISH.get(side, side)


def nearby(fix: Fix, fetch: Fetch | None = None) -> list[dict[str, Any]]:
    """Named things within NEARBY_METRES of a reading, each with a centre and its tags."""
    query = (
        f"[out:json][timeout:{int(NEARBY_SECONDS)}];"
        f"nwr(around:{NEARBY_METRES},{fix.latitude},{fix.longitude})[name]"
        '[~"^(amenity|tourism|historic|natural|leisure|place|man_made|building)$"~"."];'
        "out center 60;"
    )
    try:
        found = (fetch or _overpass)(query)
    except (OSError, json.JSONDecodeError):
        return []
    return [e for e in found.get("elements", []) if isinstance(e, dict)]


def _overpass(query: str) -> dict[str, Any]:
    request = urllib.request.Request(
        NEARBY_URL,
        data=urllib.parse.urlencode({"data": query}).encode(),
        headers={"User-Agent": POLITE},
    )
    with urllib.request.urlopen(request, timeout=NEARBY_SECONDS + 2) as reply:  # noqa: S310 — as above
        found = json.loads(reply.read() or b"{}")
    return found if isinstance(found, dict) else {}


def _centre(element: dict[str, Any]) -> tuple[float, float] | None:
    where = element.get("center") or element
    if isinstance(where.get("lat"), (int, float)) and isinstance(where.get("lon"), (int, float)):
        return float(where["lat"]), float(where["lon"])
    return None


def _kind(tags: dict[str, Any]) -> str:
    for key in ("amenity", "tourism", "historic", "natural", "leisure", "place", "man_made", "building"):
        value = str(tags.get(key, ""))
        if value in _KIND:
            return _KIND[value]
    return ""


def on_the_side(fix: Fix, side: str, elements: list[dict[str, Any]]) -> str:
    """What lies on one side of the direction of travel, nearest first, said in a sentence."""
    if not fix.moving():
        return "Jeg vet ikke hvilken vei du kjører før du er i bevegelse."
    centre_line = ((fix.heading or 0.0) + SIDES[side]) % 360
    seen = []
    for element in elements:
        where = _centre(element)
        name = str((element.get("tags") or {}).get("name", ""))
        if where is None or not name:
            continue
        off = (bearing_to(fix, *where) - centre_line + 180) % 360 - 180
        if abs(off) <= SIDE_WIDTH:
            seen.append((metres_between(fix, *where), name, _kind(element.get("tags") or {})))
    if not seen:
        return f"Jeg finner ikke noe med navn til {side} for deg akkurat her."
    seen.sort()
    said = []
    for metres, name, kind in seen[:2]:
        what = f"{name}, {kind}" if kind else name
        said.append(f"{what}, omtrent {round(metres / 50) * 50 or 50} meter unna")
    side_said = {"foran": "Foran deg", "bak": "Bak deg"}.get(side, f"Til {side}")
    return f"{side_said}: " + "; og ".join(said) + "."
