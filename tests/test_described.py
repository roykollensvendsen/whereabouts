"""Places Hermes has described, kept so the phone tells of them every time Roy passes."""

import asyncio
import time

import pytest
from starlette.testclient import TestClient

from whereabouts import described, geo, server
from whereabouts.store import Route

BRU = {
    "name": "Nidelva bru",
    "latitude": 58.45,
    "longitude": 8.77,
    "said": "Til høyre renner Nidelva ut i havet.",
}
MERDO = {"name": "Merdø", "latitude": 58.42, "longitude": 8.80, "radius_m": 400, "said": "Ute ligger Merdø."}
LANGT_UNNA = {"name": "Nordkapp", "latitude": 71.17, "longitude": 25.78, "said": "Europas nordligste punkt."}


@pytest.fixture
def route():
    return Route(None)


def call(mcp, tool, **arguments):
    result = asyncio.run(mcp.call_tool(tool, arguments))
    return result.structured_content or {"text": result.content[0].text}


def test_a_described_place_is_what_the_phone_fetches_near_roy(route):
    mcp = server.build(route)
    answer = call(mcp, "describe_places", places=[BRU, MERDO, LANGT_UNNA])
    assert answer["added"] == 3
    with TestClient(server.app(route)) as client:
        fetched = client.get("/described", params={"latitude": 58.44, "longitude": 8.78, "km": 30}).json()
    assert sorted(place["name"] for place in fetched["places"]) == ["Merdø", "Nidelva bru"]
    bru = next(place for place in fetched["places"] if place["name"] == "Nidelva bru")
    assert bru["said"] == BRU["said"]
    assert bru["radius_m"] == described.DEFAULT_RADIUS_M
    assert bru["id"]
    assert fetched["version"]


def test_places_described_are_kept_and_grow(route):
    places = described.Places(route)
    places.add([BRU])
    first = places.version()
    places.add([MERDO])
    assert len(places.near(58.44, 8.78, 30_000)) == 2
    assert places.version() != first
    # Kept in the route's own file, so a restart of the service keeps them too.
    assert len(described.Places(route).near(58.44, 8.78, 30_000)) == 2


def test_a_place_described_again_is_updated_not_added_twice(route):
    places = described.Places(route)
    places.add([BRU])
    again = places.add([{**BRU, "latitude": 58.4502, "said": "Nidelva møter havet her."}])
    assert again == {"added": 0, "updated": 1}
    [only] = places.near(58.45, 8.77, 1_000)
    assert only["said"] == "Nidelva møter havet her."


def test_a_forgotten_place_is_no_longer_told(route):
    mcp = server.build(route)
    call(mcp, "describe_places", places=[BRU, MERDO])
    assert "1" in call(mcp, "forget_described", name="merdø")["result"]
    assert [place["name"] for place in described.Places(route).near(58.44, 8.78, 30_000)] == ["Nidelva bru"]


def test_described_near_lets_hermes_see_what_is_told_already(route):
    mcp = server.build(route)
    call(mcp, "describe_places", places=[BRU])
    told = call(mcp, "described_near", latitude=58.45, longitude=8.77)["result"]
    assert [place["name"] for place in told] == ["Nidelva bru"]


def test_a_place_without_text_or_position_is_refused_with_why(route):
    mcp = server.build(route)
    answer = call(mcp, "describe_places", places=[{"latitude": 58.4, "longitude": 8.7}])
    assert answer["added"] == 0
    assert "said" in answer["said"]
    answer = call(mcp, "describe_places", places=[{"said": "Noe."}])
    assert "latitude" in answer["said"]


def test_a_place_s_radius_is_kept_within_what_a_car_can_use(route):
    places = described.Places(route)
    places.add([{**BRU, "radius_m": 1}, {**MERDO, "radius_m": 99999}])
    radii = sorted(place["radius_m"] for place in places.near(58.44, 8.78, 30_000))
    assert radii == [described.SMALLEST_RADIUS_M, described.LARGEST_RADIUS_M]


def test_one_call_describes_at_most_max_places(route):
    with pytest.raises(ValueError, match="steder"):
        described.Places(route).add([BRU] * (described.MAX_PLACES + 1))


def test_sights_near_a_point_name_what_is_worth_describing(route):
    found = {
        "elements": [
            {
                "type": "node",
                "lat": 58.461,
                "lon": 8.772,
                "tags": {"name": "Tyholmen", "historic": "district", "wikipedia": "no:Tyholmen"},
            },
            {
                "type": "way",
                "center": {"lat": 58.46, "lon": 8.77},
                "tags": {"name": "Kirken", "building": "church"},
            },
            {"type": "relation", "tags": {"name": "Uten sted"}},
        ]
    }
    asked = []

    def fetch(query):
        asked.append(query)
        return found

    sights = call(server.build(route, nearby=fetch), "sights_near", latitude=58.46, longitude=8.77, km=50)[
        "result"
    ]
    assert "around:5000," in asked[0]  # never wider than five kilometres
    assert [sight["name"] for sight in sights] == ["Tyholmen", "Kirken"]
    assert sights[0]["wikipedia"] == "no:Tyholmen"


def test_sights_along_a_road_are_named_in_the_order_passed(route):
    road = [(58.46, 8.77), (58.50, 8.80), (58.55, 8.83), (58.62, 8.93)]  # Arendal towards Tvedestrand
    found = {
        "elements": [
            {"type": "node", "lat": 58.62, "lon": 8.93, "tags": {"name": "Tvedestrand", "place": "town"}},
            {"type": "node", "lat": 58.46, "lon": 8.77, "tags": {"name": "Arendal", "place": "town"}},
            {
                "type": "way",
                "center": {"lat": 58.5, "lon": 8.8},
                "tags": {"name": "Fv410", "highway": "primary"},
            },
            {"type": "node", "lat": 58.55, "lon": 8.83, "tags": {"name": "Songevatnet", "natural": "water"}},
        ]
    }
    asked = []

    def fetch(query):
        asked.append(query)
        return found

    mcp = server.build(route, nearby=fetch, router=lambda _a, _b: road)
    answer = call(
        mcp, "sights_along", from_latitude=58.46, from_longitude=8.77, to_latitude=58.62, to_longitude=8.93
    )
    assert [sight["name"] for sight in answer["found"]] == ["Arendal", "Fv410", "Songevatnet", "Tvedestrand"]
    assert [sight["kind"] for sight in answer["found"]] == ["by", "vei", "vann", "by"]
    assert "around:" in asked[0]
    assert answer["km"] > 0


def test_no_road_between_two_points_is_said_plainly(route):
    mcp = server.build(route, router=lambda _a, _b: [])
    answer = call(
        mcp, "sights_along", from_latitude=58.46, from_longitude=8.77, to_latitude=58.62, to_longitude=8.93
    )
    assert answer["found"] == []


def test_a_note_left_by_voice_is_told_where_roy_was(route):
    route.add(geo.Fix(58.5, 8.9, 90, 20, time.time()))
    mcp = server.build(route)
    assert "lagt igjen" in call(mcp, "leave_note", said="Husk å kjøpe ved på Shell")["result"]
    [note] = described.Places(route).near(58.5, 8.9, 100)
    assert note["kind"] == described.NOTE
    assert note["said"] == "En melding du la igjen her: Husk å kjøpe ved på Shell"


def test_a_note_is_never_merged_with_a_place_or_another_note(route):
    route.add(geo.Fix(58.5, 8.9, 90, 20, time.time()))
    described.Places(route).add(
        [{"name": "Shell", "latitude": 58.5, "longitude": 8.9, "said": "En bensinstasjon."}]
    )
    mcp = server.build(route)
    call(mcp, "leave_note", said="Første")
    call(mcp, "leave_note", said="Andre")
    assert len(described.Places(route).near(58.5, 8.9, 100)) == 3


def test_a_note_is_forgotten_by_its_words(route):
    route.add(geo.Fix(58.5, 8.9, 90, 20, time.time()))
    mcp = server.build(route)
    call(mcp, "leave_note", said="Husk å kjøpe ved")
    call(mcp, "forget_described", name="kjøpe ved")
    assert described.Places(route).near(58.5, 8.9, 100) == []


def test_no_note_is_left_without_knowing_where_roy_is(route):
    mcp = server.build(route)
    assert "vet ikke" in call(mcp, "leave_note", said="Hei")["result"]
    route.add(geo.Fix(58.5, 8.9, 90, 20, time.time() - 3600))
    assert "vet ikke" in call(mcp, "leave_note", said="Hei")["result"]


def test_news_is_told_only_until_it_fades(route):
    mcp = server.build(route)
    news = {**BRU, "said": "Tvedestrandsposten skrev i går at brua stenges til helgen."}
    assert call(mcp, "add_local_news", news=[news], days=3)["added"] == 1
    [told] = described.Places(route).near(58.45, 8.77, 1_000)
    assert told["kind"] == described.NEWS
    with route.lock, route.db:
        route.db.execute("UPDATE described SET until = ?", (time.time() - 1,))
    assert described.Places(route).near(58.45, 8.77, 1_000) == []


def test_news_never_replaces_the_description_of_a_place(route):
    places = described.Places(route)
    places.add([BRU])
    places.add([{**BRU, "said": "Ny nyhet."}], kind=described.NEWS, until=time.time() + 3600)
    assert sorted(place["kind"] for place in places.near(58.45, 8.77, 1_000)) == ["news", "place"]


def test_only_what_lies_along_the_route_is_kept_from_the_boxes(route):
    now = time.time()
    for i in range(6):
        route.add(geo.Fix(58.46 + i * 0.01, 8.77, 0, 20, now - 3600 + i * 60))
    described.Places(route).add(
        [{"name": "Allerede", "latitude": 58.48, "longitude": 8.77, "said": "Kjent."}]
    )
    found = {
        "elements": [
            {"type": "node", "lat": 58.47, "lon": 8.771, "tags": {"name": "Ved veien", "natural": "water"}},
            {"type": "node", "lat": 58.48, "lon": 8.7701, "tags": {"name": "Allerede", "place": "hamlet"}},
            {"type": "node", "lat": 58.47, "lon": 8.90, "tags": {"name": "Langt unna", "place": "hamlet"}},
        ]
    }
    asked = []

    def fetch(query):
        asked.append(query)
        return found

    answer = call(server.build(route, nearby=fetch), "sights_on_route_taken", hours=2)
    assert [sight["name"] for sight in answer["found"]] == ["Ved veien"]
    # The route itself is never sent: only a box around it.
    assert "around:" not in asked[0]
    assert "bbox:" in asked[0]


def test_a_pretend_drive_gets_the_road_between_two_named_places(route):
    road = [(58.46, 8.77), (58.55, 8.83), (58.62, 8.93)]
    named_places = {"Arendal": (58.46, 8.77), "Tvedestrand": (58.62, 8.93)}
    asked = []

    def router(start, end):
        asked.append((start, end))
        return road

    application = server.app(route, router=router, finder=named_places.get)
    with TestClient(application) as client:
        found = client.get("/road", params={"from": "Arendal", "to": "58.62,8.93"}).json()
        missing = client.get("/road", params={"from": "Atlantis", "to": "Tvedestrand"})
    assert found["points"] == [list(point) for point in road]
    assert asked == [((58.46, 8.77), (58.62, 8.93))]
    assert missing.status_code == 404
    # A pretend drive is never kept as part of the route.
    assert route.latest() is None
