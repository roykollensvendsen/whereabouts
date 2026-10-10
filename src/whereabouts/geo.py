"""Readings, directions and what is around them: the arithmetic, and OpenStreetMap.

Begun in voice-integration as `voice_bridge.moving`, and moved here when where
Roy is became a service of its own.
"""

from __future__ import annotations

import itertools
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
#: A reading older than this is not "where you are now". A phone standing still
#: gets few new fixes, so this is long; moving, it sends far more often.
FRESH_SECONDS = 600.0
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
    "town": "by",
    "isolated_dwelling": "gård",
    "neighbourhood": "boligfelt",
    "water": "vann",
    "lake": "innsjø",
    "river": "elv",
    "stream": "bekk",
    "bridge": "bru",
    "tunnel": "tunnel",
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


def sights(
    latitude: float, longitude: float, metres: float, fetch: Fetch | None = None
) -> list[dict[str, Any]]:
    """Named sights around a point, for planning a tour: what, where, and its Wikipedia article."""
    query = (
        f"[out:json][timeout:{int(NEARBY_SECONDS)}];"
        f"nwr(around:{round(metres)},{latitude},{longitude})[name]"
        '[~"^(tourism|historic|natural|man_made|wikipedia)$"~"."];'
        "out center 80;"
    )
    try:
        found = (fetch or _overpass)(query)
    except (OSError, json.JSONDecodeError):
        return []
    listed = []
    for element in found.get("elements", []):
        centre = _centre(element) if isinstance(element, dict) else None
        if centre is None:
            continue
        tags = element.get("tags", {})
        listed.append(
            {
                "name": tags.get("name", ""),
                "kind": _kind(tags),
                "latitude": round(centre[0], 6),
                "longitude": round(centre[1], 6),
                "wikipedia": tags.get("wikipedia"),
            }
        )
    return listed


#: The public road router, asked for the road between two points.
ROAD_URL = "https://router.project-osrm.org/route/v1/driving/"
#: A whole road takes longer to search than one spot; planning is not in a hurry.
ALONG_SECONDS = 60.0
#: The roads worth naming: those a car drives through on, not the side streets of a town.
THROUGH_ROADS = '"^(motorway|trunk|primary|secondary|tertiary|unclassified)$"'
#: How far from the road, in metres, a thing still counts as along it.
ALONG_METRES = 400
#: One point of the road every this many metres is enough to follow it.
ALONG_STEP_METRES = 800


#: The public place-name search, asked for where a named place is.
NAMES_URL = "https://nominatim.openstreetmap.org/search"


def place_named(name: str) -> tuple[float, float] | None:
    """Where a place by this name is, in Norway first, or None when it cannot be found."""
    query = urllib.parse.urlencode({"q": name, "format": "json", "limit": 1, "countrycodes": "no"})
    request = urllib.request.Request(f"{NAMES_URL}?{query}", headers={"User-Agent": POLITE})  # noqa: S310 — fixed https
    try:
        with urllib.request.urlopen(request, timeout=NEARBY_SECONDS + 2) as reply:  # noqa: S310 — as above
            found = json.loads(reply.read() or b"[]")
        return float(found[0]["lat"]), float(found[0]["lon"])
    except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
        return None


def where(
    said: str, finder: Callable[[str], tuple[float, float] | None] | None = None
) -> tuple[float, float] | None:
    """A point given as "latitude,longitude", or the place by that name."""
    parts = said.split(",")
    if len(parts) == 2:  # noqa: PLR2004 — latitude and longitude
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            pass
    return (finder or place_named)(said.strip()) if said.strip() else None


def road_between(start: tuple[float, float], end: tuple[float, float]) -> list[tuple[float, float]]:
    """The road between two points as latitude and longitude pairs, or none when the router is down."""
    url = f"{ROAD_URL}{start[1]},{start[0]};{end[1]},{end[0]}?overview=full&geometries=geojson"
    request = urllib.request.Request(url, headers={"User-Agent": POLITE})  # noqa: S310 — a fixed https address
    try:
        with urllib.request.urlopen(request, timeout=NEARBY_SECONDS + 2) as reply:  # noqa: S310 — as above
            found = json.loads(reply.read() or b"{}")
        line = found["routes"][0]["geometry"]["coordinates"]
    except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError):
        return []
    return [(float(lat), float(lon)) for lon, lat in line]


def thinned(road: list[tuple[float, float]], step: float = ALONG_STEP_METRES) -> list[tuple[float, float]]:
    """Every `step` metres of a road, with both its ends."""
    if len(road) < 2:  # noqa: PLR2004 — a road has two ends
        return road
    kept, since = [road[0]], 0.0
    for before, here in itertools.pairwise(road):
        since += metres_between(Fix(before[0], before[1], None, None, 0.0), here[0], here[1])
        if since >= step:
            kept.append(here)
            since = 0.0
    if kept[-1] != road[-1]:
        kept.append(road[-1])
    return kept


def sights_along(road: list[tuple[float, float]], fetch: Fetch | None = None) -> list[dict[str, Any]]:
    """What has a name along a road: places, farms, water, bridges and sights, in the order passed."""
    points = thinned(road)
    if not points:
        return []
    line = ",".join(f"{lat:.5f},{lon:.5f}" for lat, lon in points)
    query = (
        f"[out:json][timeout:{int(ALONG_SECONDS)}];"
        f"nwr(around:{ALONG_METRES},{line})[name]"
        '[~"^(place|tourism|historic|natural|water|man_made|wikipedia|bridge)$"~"."];'
        "out center 400;"
        # Roads with their whole line, so a side road is placed where it meets the route.
        f"way(around:{ALONG_METRES // 4},{line})[highway~{THROUGH_ROADS}][name];"
        "out geom 200;"
    )
    try:
        found = fetch(query) if fetch else _overpass(query, ALONG_SECONDS)
    except (OSError, json.JSONDecodeError):
        return []
    return _in_order(found.get("elements", []), points)


#: The widest stretch, in degrees of latitude or longitude, searched as one box.
BOX_DEGREES = 0.15


def sights_on_route(route: list[tuple[float, float]], fetch: Fetch | None = None) -> list[dict[str, Any]]:
    """What has a name along a route already driven, in the order passed.

    Overpass is asked for boxes around the route, never for the route itself,
    so where Roy drove stays on this machine; the box is narrowed to the road
    here.
    """
    points = thinned(route)
    found: list[dict[str, Any]] = []
    for box in _boxes(points):
        south, west, north, east = box
        pad = ALONG_METRES / 111_320
        bbox = f"{south - pad:.4f},{west - pad * 2:.4f},{north + pad:.4f},{east + pad * 2:.4f}"
        query = (
            f"[out:json][timeout:{int(ALONG_SECONDS)}][bbox:{bbox}];"
            '(nwr[name][~"^(place|tourism|historic|natural|water|man_made|wikipedia|bridge)$"~"."];'
            f"way[highway~{THROUGH_ROADS}][name];);"
            "out center 2000;"
        )
        try:
            found += (fetch(query) if fetch else _overpass(query, ALONG_SECONDS)).get("elements", [])
        except (OSError, json.JSONDecodeError):
            continue
    here = [Fix(lat, lon, None, None, 0.0) for lat, lon in points]
    # RULE: only what lies along the route is kept from the boxes
    close = [
        element
        for element in found
        if isinstance(element, dict)
        and (centre := _centre(element)) is not None
        and any(metres_between(point, *centre) <= ALONG_METRES for point in here)
    ]
    return _in_order(close, points)


def _boxes(points: list[tuple[float, float]]) -> list[tuple[float, float, float, float]]:
    """South, west, north and east of each stretch of the route no wider than BOX_DEGREES."""
    boxes: list[tuple[float, float, float, float]] = []
    stretch: list[tuple[float, float]] = []
    for point in points:
        trial = [*stretch, point]
        lats, lons = [p[0] for p in trial], [p[1] for p in trial]
        if stretch and (max(lats) - min(lats) > BOX_DEGREES or max(lons) - min(lons) > BOX_DEGREES):
            boxes.append(_box(stretch))
            stretch = [stretch[-1], point]
        else:
            stretch = trial
    if stretch:
        boxes.append(_box(stretch))
    return boxes


def _box(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    return min(lats), min(lons), max(lats), max(lons)


def _in_order(elements: list[Any], points: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """Each named thing once, with what it is and where, in the order the points pass it."""
    listed: dict[str, dict[str, Any]] = {}
    for element in elements:
        centre = _meeting(element, points) if isinstance(element, dict) else None
        if centre is None:
            continue
        tags = element.get("tags", {})
        name = str(tags.get("name", ""))
        if not name or name in listed:
            continue
        nearest = min(range(len(points)), key=lambda i: _apart(points[i], centre))
        listed[name] = {
            "name": name,
            "kind": "vei" if "highway" in tags else _kind(tags),
            "latitude": round(centre[0], 6),
            "longitude": round(centre[1], 6),
            "wikipedia": tags.get("wikipedia"),
            # A road's number, such as "Fv 410", and anything else the map knows that is worth saying.
            "ref": tags.get("ref"),
            "population": tags.get("population"),
            "height": tags.get("height") or tags.get("ele"),
            "order": nearest,
        }
    return sorted(listed.values(), key=lambda sight: sight["order"])


def _meeting(element: dict[str, Any], points: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Where a thing is: for a road with its line, the point of it nearest the route, where it meets it."""
    line = element.get("geometry")
    if isinstance(line, list) and line and points:
        # RULE: a side road is placed where it meets the route
        vertices = [(float(v["lat"]), float(v["lon"])) for v in line if "lat" in v and "lon" in v]
        if vertices:
            return min(vertices, key=lambda v: min(_apart(v, p) for p in points))
    return _centre(element)


def _apart(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + ((a[1] - b[1]) * 0.5) ** 2


def _overpass(query: str, seconds: float = NEARBY_SECONDS) -> dict[str, Any]:
    request = urllib.request.Request(
        NEARBY_URL,
        data=urllib.parse.urlencode({"data": query}).encode(),
        headers={"User-Agent": POLITE},
    )
    with urllib.request.urlopen(request, timeout=seconds + 2) as reply:  # noqa: S310 — as above
        found = json.loads(reply.read() or b"{}")
    return found if isinstance(found, dict) else {}


def _centre(element: dict[str, Any]) -> tuple[float, float] | None:
    where = element.get("center") or element
    if isinstance(where.get("lat"), (int, float)) and isinstance(where.get("lon"), (int, float)):
        return float(where["lat"]), float(where["lon"])
    return None


def _kind(tags: dict[str, Any]) -> str:
    for key in (
        "amenity",
        "tourism",
        "historic",
        "natural",
        "water",
        "leisure",
        "place",
        "man_made",
        "building",
        "bridge",
    ):
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
