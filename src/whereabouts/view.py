"""What Roy can see ahead: half a circle in front of the car, cut short by hills and forest.

Roy, 2026-10-10: tell of things as they come into view, and show on the map
what can be seen, shaped by the land and kept up to date while he drives.
The height of the ground, and whether it is forest, comes from Kartverket's
height service and is kept on this machine, so a road driven before costs
nothing to look at again.
"""

from __future__ import annotations

import json
import math
import struct
import threading
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING, Any

from whereabouts import geo

if TYPE_CHECKING:
    from collections.abc import Callable

    from whereabouts.store import Route

    #: Asks for the ground at up to BATCH points (longitude, latitude): height and land cover each.
    Ground = Callable[[list[tuple[float, float]]], list[tuple[float, str]]]

HEIGHTS_URL = "https://ws.geonorge.no/hoydedata/v1/punkt"
#: The most points the height service answers in one request.
BATCH = 50
#: Heights are kept on a grid this fine, in degrees of latitude (about 50 m); in longitude, twice this.
GRID = 0.00045
#: How wide the view is, either side of straight ahead, in degrees, and how far apart its rays are.
HALF_WIDTH = 90
RAY_STEP = 10
#: How far a ray looks, and how often along it the ground is asked for, in metres.
FARTHEST = 3000
SAMPLE_STEP = 50
#: Eyes in a car, above the ground.
EYES = 1.2
#: What stands up from the land: forest hides what is behind it.
# Roy, 2026-10-10: the view was far too big; little is seen that far. Built-up land, and land the
# height service does not name, hide what is behind them too.
COVER = {
    "Skog": 12.0,
    "Tettbebyggelse": 10.0,
    "BymessigBebyggelse": 15.0,
    "Industriområde": 10.0,
    "": 6.0,
}
#: Nearer than this the grid cannot tell the road and its verges from the forest beside it.
OPEN_NEAR = 50
#: What is looked for stands this high above its ground: a house, a mast's foot, a lake's far shore.
TARGET = 3.0


class Heights:
    """The ground's height and cover, kept on a grid in the route's file."""

    def __init__(self, route: Route, ground: Ground | None = None) -> None:
        """Keep heights beside the route; `ground` asks the height service."""
        self.lock = route.lock
        self.db = route.db
        self.ground = ground or ask_kartverket
        self.asking = threading.Lock()
        with self.lock, self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS heights (cell TEXT PRIMARY KEY, z REAL, cover TEXT)")

    def at(self, points: list[tuple[float, float]]) -> list[tuple[float, str]]:
        """The ground's height and cover at each (latitude, longitude), asking only for what is not kept."""
        cells = [_cell(lat, lon) for lat, lon in points]
        known = self._known(set(cells))
        missing = sorted({cell for cell in cells if cell not in known})
        with self.asking:
            for start in range(0, len(missing), BATCH):
                chunk = missing[start : start + BATCH]
                try:
                    answers = self.ground([_centre(cell)[::-1] for cell in chunk])
                except (OSError, ValueError, KeyError, json.JSONDecodeError):
                    continue
                with self.lock, self.db:
                    self.db.executemany(
                        "INSERT OR REPLACE INTO heights VALUES (?, ?, ?)",
                        [(cell, z, cover) for cell, (z, cover) in zip(chunk, answers, strict=False)],
                    )
                known.update(dict(zip(chunk, answers, strict=False)))
        return [known.get(cell, (math.nan, "")) for cell in cells]

    def _known(self, cells: set[str]) -> dict[str, tuple[float, str]]:
        found: dict[str, tuple[float, str]] = {}
        listed = list(cells)
        with self.lock:
            for start in range(0, len(listed), 500):
                chunk = listed[start : start + 500]
                marks = ",".join("?" * len(chunk))
                for cell, z, cover in self.db.execute(
                    f"SELECT cell, z, cover FROM heights WHERE cell IN ({marks})",  # noqa: S608 — only placeholders
                    chunk,
                ):
                    found[cell] = (z, cover)
        return found


#: How far either side of a driven road the phone is given the land, in metres: as far as a view reaches.
BAND = FARTHEST
#: One band centre every this many metres along a road.
BAND_STEP = 500


def band_cells(points: list[tuple[float, float]]) -> list[str]:
    """Every grid cell within BAND of the given road points: the land a view from that road can reach."""
    cells: set[str] = set()
    rows = round(BAND / 111_320 / GRID)
    for latitude, longitude in points:
        row0, col0 = round(latitude / GRID), round(longitude / (GRID * 2))
        across = max(1, round(rows * 0.5 / max(math.cos(math.radians(latitude)), 0.1)))
        for row in range(row0 - rows, row0 + rows + 1):
            for col in range(col0 - across, col0 + across + 1):
                if ((row - row0) / rows) ** 2 + ((col - col0) / across) ** 2 <= 1:
                    cells.add(f"{row}:{col}")
    return sorted(cells)


def fill(heights: Heights, cells: list[str]) -> int:
    """Ask the height service for every cell not yet kept. Returns how many were asked."""
    known = heights._known(set(cells))  # noqa: SLF001 — the same store, read in bulk
    missing = [cell for cell in cells if cell not in known]
    for start in range(0, len(missing), BATCH * 20):
        heights.at([_centre(cell) for cell in missing[start : start + BATCH * 20]])
    return len(missing)


def packed(heights: Heights, latitude: float, longitude: float, metres: float) -> bytes:
    """The kept land around a point, small enough for the phone: a header line, then 11 bytes a cell.

    Each cell is its grid row and column (int32 each), its height in decimetres
    (int16) and its land cover as an index into the header's codes (uint8).
    """
    dlat = metres / 111_320
    dlon = dlat / max(math.cos(math.radians(latitude)), 0.1)
    rows = (round((latitude - dlat) / GRID), round((latitude + dlat) / GRID))
    cols = (round((longitude - dlon) / (GRID * 2)), round((longitude + dlon) / (GRID * 2)))
    codes = sorted(COVER)
    index = {name: i for i, name in enumerate(codes)}
    with heights.lock:
        found = heights.db.execute("SELECT cell, z, cover FROM heights").fetchall()
    body = bytearray()
    count = 0
    for cell, z, cover in sorted(found, key=lambda row: tuple(int(x) for x in row[0].split(":"))):
        row, col = (int(x) for x in cell.split(":"))
        if not (rows[0] <= row <= rows[1] and cols[0] <= col <= cols[1]) or z is None or math.isnan(z):
            continue
        body += struct.pack("<iihB", row, col, max(-32768, min(32767, round(z * 10))), index.get(cover, 255))
        count += 1
    header = {
        "grid": GRID,
        "count": count,
        "eyes": EYES,
        "target": TARGET,
        "open_near": OPEN_NEAR,
        "half_width": HALF_WIDTH,
        "ray_step": RAY_STEP,
        "sample_step": SAMPLE_STEP,
        "farthest": FARTHEST,
        "codes": [[name, COVER[name]] for name in codes],
    }
    return json.dumps(header).encode() + b"\n" + bytes(body)


def view(heights: Heights, latitude: float, longitude: float, heading: float) -> list[dict[str, Any]]:
    """Each ray across the half circle ahead: its bearing, how far it sees, and which distances it sees."""
    here = geo.Fix(latitude, longitude, None, None, 0.0)
    bearings = [(heading + turn) % 360 for turn in range(-HALF_WIDTH, HALF_WIDTH + 1, RAY_STEP)]
    steps = list(range(SAMPLE_STEP, FARTHEST + 1, SAMPLE_STEP))
    points = [(latitude, longitude)] + [
        _ahead(here, bearing, metres) for bearing in bearings for metres in steps
    ]
    ground = heights.at(points)
    eyes = (ground[0][0] if not math.isnan(ground[0][0]) else 0.0) + EYES
    rays = []
    for index, bearing in enumerate(bearings):
        along = ground[1 + index * len(steps) : 1 + (index + 1) * len(steps)]
        seen = sight(eyes, [(metres, z, cover) for metres, (z, cover) in zip(steps, along, strict=True)])
        # RULE: the view reaches only as far as the ground is seen without a break
        reach = 0
        for metres in steps:
            if metres not in seen:
                break
            reach = metres
        rays.append({"bearing": round(bearing, 1), "reach": reach, "seen": seen})
    return rays


def sight(eyes: float, line: list[tuple[int, float, str]]) -> list[int]:
    """The distances along one line of ground that can be seen from `eyes` metres above the sea."""
    highest = -math.inf
    seen = []
    for metres, z, cover in line:
        if math.isnan(z):
            break
        # RULE: what lies behind higher ground or forest cannot be seen
        if math.atan2(z + TARGET - eyes, metres) >= highest:
            seen.append(metres)
        standing = COVER.get(cover, 0.0) if metres > OPEN_NEAR else 0.0
        highest = max(highest, math.atan2(z + standing - eyes, metres))
    return seen


def outline(latitude: float, longitude: float, rays: list[dict[str, Any]]) -> list[list[float]]:
    """The view as a shape for the map: from the car out along each ray as far as it sees, and back."""
    here = geo.Fix(latitude, longitude, None, None, 0.0)
    edge = [list(_ahead(here, ray["bearing"], max(ray["reach"], SAMPLE_STEP // 2))) for ray in rays]
    return [[latitude, longitude], *edge, [latitude, longitude]]


def ask_kartverket(points: list[tuple[float, float]]) -> list[tuple[float, str]]:
    """Kartverket's height and land cover at up to BATCH points given as (longitude, latitude)."""
    query = urllib.parse.urlencode(
        {"koordsys": 4258, "punkter": json.dumps([[lon, lat] for lon, lat in points])}
    )
    request = urllib.request.Request(f"{HEIGHTS_URL}?{query}", headers={"User-Agent": geo.POLITE})  # noqa: S310 — fixed https
    with urllib.request.urlopen(request, timeout=15) as reply:  # noqa: S310 — as above
        found = json.loads(reply.read() or b"{}")
    return [
        (float(p.get("z") if p.get("z") is not None else math.nan), str(p.get("terreng") or ""))
        for p in found["punkter"]
    ]


def _ahead(here: geo.Fix, bearing: float, metres: float) -> tuple[float, float]:
    """The point `metres` from `here` along `bearing`."""
    r = math.radians
    angular = metres / 6_371_000
    lat1, lon1, b = r(here.latitude), r(here.longitude), r(bearing)
    lat2 = math.asin(math.sin(lat1) * math.cos(angular) + math.cos(lat1) * math.sin(angular) * math.cos(b))
    lon2 = lon1 + math.atan2(
        math.sin(b) * math.sin(angular) * math.cos(lat1), math.cos(angular) - math.sin(lat1) * math.sin(lat2)
    )
    return math.degrees(lat2), math.degrees(lon2)


def _cell(latitude: float, longitude: float) -> str:
    return f"{round(latitude / GRID)}:{round(longitude / (GRID * 2))}"


def _centre(cell: str) -> tuple[float, float]:
    row, column = cell.split(":")
    return int(row) * GRID, int(column) * GRID * 2
