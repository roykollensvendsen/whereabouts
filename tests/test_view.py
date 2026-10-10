"""What can be seen ahead: half a circle, cut short by hills and forest."""

import math

import pytest
from starlette.testclient import TestClient

from whereabouts import server, view
from whereabouts.store import Route


@pytest.fixture
def route():
    return Route(None)


def test_what_lies_behind_higher_ground_or_forest_cannot_be_seen():
    flat = [(100, 10.0, ""), (200, 10.0, ""), (300, 10.0, "")]
    assert view.sight(11.2, flat) == [100, 200, 300]
    ridge = [(100, 10.0, ""), (200, 60.0, ""), (300, 10.0, ""), (400, 10.0, "")]
    assert view.sight(11.2, ridge) == [100, 200]
    forest = [(100, 10.0, ""), (200, 10.0, "Skog"), (300, 10.0, ""), (400, 10.0, "")]
    assert view.sight(11.2, forest) == [100, 200]
    # By the road the grid cannot tell the verge from the forest: it does not block.
    verge = [(100, 10.0, "Skog"), (200, 10.0, ""), (300, 10.0, "")]
    assert view.sight(11.2, verge) == [100, 200, 300]
    # A hill far off rises above a forest near: it is seen.
    hill = [(200, 10.0, "Skog"), (2000, 300.0, "")]
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
            out.append((200.0 if 900 <= north <= 1100 else 10.0, ""))
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
