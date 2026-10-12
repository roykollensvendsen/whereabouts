"""What can be seen ahead: half a circle, cut short by hills and forest."""

import json
import math
import struct
import time

import pytest
from starlette.testclient import TestClient

from whereabouts import geo, server, view
from whereabouts.store import Route


@pytest.fixture
def route():
    return Route(None)


def test_what_lies_behind_higher_ground_or_forest_cannot_be_seen():
    flat = [(100, 10.0, "DyrketMark"), (200, 10.0, "DyrketMark"), (300, 10.0, "DyrketMark")]
    assert view.sight(11.2, flat) == [100, 200, 300]
    ridge = [(100, 10.0, "Myr"), (200, 60.0, "Myr"), (300, 10.0, "Myr"), (400, 10.0, "Myr")]
    assert view.sight(11.2, ridge) == [100, 200]
    forest = [(100, 10.0, "Myr"), (200, 10.0, "Skog"), (300, 10.0, "Myr"), (400, 10.0, "Myr")]
    assert view.sight(11.2, forest) == [100, 200]
    # By the road the grid cannot tell the verge from the forest: it does not block.
    verge = [(50, 10.0, "Skog"), (200, 10.0, "DyrketMark"), (300, 10.0, "DyrketMark")]
    assert view.sight(11.2, verge) == [50, 200, 300]
    # Built-up land hides what lies behind it.
    town = [(100, 10.0, "Tettbebyggelse"), (200, 10.0, "DyrketMark")]
    assert view.sight(11.2, town) == [100]
    # A hill far off rises above a forest near: it is seen.
    hill = [(200, 10.0, "Skog"), (2000, 300.0, "Myr")]
    assert view.sight(11.2, hill) == [200, 2000]


def test_heights_are_kept_so_a_road_driven_before_is_not_asked_again(route):
    asked = []

    def ground(points):
        asked.append(len(points))
        return [(10.0, "DyrketMark") for _ in points]

    heights = view.Heights(route, ground)
    first = heights.at([(58.5, 8.8), (58.5005, 8.8), (58.6, 8.9)])
    assert first[0] == (10.0, "DyrketMark")
    again = heights.at([(58.5, 8.8), (58.6, 8.9)])
    assert again == [(10.0, "DyrketMark"), (10.0, "DyrketMark")]
    assert sum(asked) == 3
    # Never more than the service takes at once.
    heights.at([(58.0 + i * 0.01, 8.0) for i in range(120)])
    assert max(asked) <= view.BATCH


def test_the_view_is_half_a_circle_ahead_and_drawn_as_a_shape(route):
    def ground(points):
        # Flat land, but a wall of hills 1 km to the north.
        out = []
        for _lon, lat in points:
            north = (lat - 58.5) * 111_320
            out.append((200.0 if 900 <= north <= 1100 else 10.0, "DyrketMark"))
        return out

    with TestClient(server.app(route, ground=ground)) as client:
        seen = client.get("/view", params={"latitude": 58.5, "longitude": 8.8, "heading": 0}).json()
    rays = seen["rays"]
    assert rays[0]["bearing"] == 270.0
    assert len(rays) == 2 * view.HALF_WIDTH // view.RAY_STEP + 1
    ahead = next(ray for ray in rays if ray["bearing"] == 0.0)
    east = next(ray for ray in rays if ray["bearing"] == 90.0)
    assert ahead["reach"] == 900  # the face of the hills, and nothing behind them
    assert east["reach"] == view.FARTHEST
    assert seen["outline"][0] == seen["outline"][-1] == [58.5, 8.8]
    assert not any(math.isnan(x) for point in seen["outline"] for x in point)


def test_the_view_reaches_only_as_far_as_the_ground_is_seen_without_a_break(route):
    def ground(points):
        # A ridge 300 m north hides the valley behind it; a hilltop 2 km north rises above it.
        out = []
        for _lon, lat in points:
            north = (lat - 58.5) * 111_320
            height = 60.0 if 280 <= north <= 320 else 400.0 if 1950 <= north <= 2050 else 10.0
            out.append((height, "DyrketMark"))
        return out

    with TestClient(server.app(route, ground=ground)) as client:
        rays = client.get("/view", params={"latitude": 58.5, "longitude": 8.8, "heading": 0}).json()["rays"]
    ahead = next(ray for ray in rays if ray["bearing"] == 0.0)
    assert ahead["reach"] == 300  # drawn only to the ridge
    assert any(1950 <= metres <= 2050 for metres in ahead["seen"])  # yet the hilltop can still be told of


def test_the_land_along_a_driven_road_is_packed_for_the_phone(route):
    now = time.time() - 600
    for i in range(3):
        route.add(geo.Fix(58.50 + i * 0.002, 8.80, 0.0, 20, now + i * 10))

    def ground(points):
        return [(12.5, "Skog") for _ in points]

    with TestClient(server.app(route, ground=ground)) as client:
        client.get("/land.bin", params={"latitude": 58.5, "longitude": 8.8, "km": 5})  # starts the filling
        time.sleep(1.5)
        body = client.get("/land.bin", params={"latitude": 58.5, "longitude": 8.8, "km": 5}).content
    header, cells = body.split(b"\n", 1)
    about = json.loads(header)
    assert about["count"] == len(cells) // 11
    assert about["count"] > 1000  # the band around the road, on both sides
    _row, _col, decimetres, code = struct.unpack("<iihB", cells[:11])
    assert decimetres == 125
    assert about["codes"][code][0] == "Skog"


def test_where_land_is_kept_is_shown_as_blocks(route):
    heights = view.Heights(route, lambda points: [(10.0, "Skog") for _ in points])
    # Two neighbouring 1 km blocks, fully kept, on one row: one rectangle.
    row0, col0 = 130_000, 9_780
    cells = [
        (row * view.GRID, col * view.GRID * 2)
        for row in range(row0, row0 + view.BLOCK)
        for col in range(col0, col0 + 2 * view.BLOCK)
    ]
    heights.at(cells)
    shapes = view.coverage(heights)
    assert len(shapes) == 1
    (south, west), (north, east) = shapes[0]
    assert north > south
    assert east - west > (north - south)  # two blocks wide, one tall
