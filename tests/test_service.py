"""The service end to end: a reading in, an answer out over MCP, and the route on a map."""

import asyncio
import time

import pytest
from starlette.testclient import TestClient

from whereabouts import cli, geo, places, server
from whereabouts.store import KEPT_DAYS, Route

SKUGGEVIK = {"latitude": 58.6, "longitude": 9.0, "heading": 90, "speed": 60 / 3.6}


def named(_fix):
    return "Skuggevik"


@pytest.fixture
def route():
    return Route(None)


def call(mcp, tool, **arguments):
    """One tool, called the way an MCP client calls it, and its structured answer."""
    result = asyncio.run(mcp.call_tool(tool, arguments))
    return result.structured_content or {"text": result.content[0].text}


def test_a_reading_sent_in_is_where_hermes_is_told_roy_is(route):
    """The walking skeleton: phone to service to Hermes, in one path."""
    mcp = server.build(route, namer=named, nearby=lambda _q: {"elements": []})
    with TestClient(mcp.streamable_http_app()) as client:
        assert client.post("/reading", json=SKUGGEVIK).json() == {"kept": True}
    answer = call(mcp, "where_am_i")
    assert answer["known"] is True
    assert answer["said"].startswith("Du er i Skuggevik, på vei øst i omtrent 60 kilometer i timen.")
    assert answer["direction"] == "øst"
    assert answer["km_h"] == 60
    # The figures behind the sentence, for Hermes to work with: Roy, 2026-10-10.
    assert (answer["latitude"], answer["longitude"]) == (58.6, 9.0)
    assert answer["heading_degrees"] == 90.0
    assert answer["speed_m_s"] == round(60 / 3.6, 2)
    assert answer["measured_at"].startswith(time.strftime("%Y-%m-%d"))


def test_nothing_known_is_said_plainly(route):
    mcp = server.build(route, namer=named)
    assert call(mcp, "where_am_i") == {"known": False, "said": "Jeg vet ikke hvor du er ennå."}


def test_a_reading_that_is_not_one_is_refused(route):
    with TestClient(server.app(route, namer=named)) as client:
        assert client.post("/reading", content=b"[1, 2]").status_code == 400


def test_the_route_is_a_line_on_a_map(route):
    now = time.time()
    route.add(geo.Fix(58.6, 9.0, 90, 16, now - 120))
    route.add(geo.Fix(58.6, 9.02, 90, 16, now - 60))
    with TestClient(server.app(route, namer=named)) as client:
        line = client.get("/route.geojson?minutes=10").json()
        page = client.get("/map").text
    assert line["geometry"]["coordinates"] == [[9.0, 58.6], [9.02, 58.6]]
    assert "route.geojson" in page


def test_the_route_taken_is_said_in_kilometres_and_minutes(route):
    now = time.time()
    route.add(geo.Fix(58.6, 9.0, 90, 16, now - 600))
    route.add(geo.Fix(58.6, 9.1, 90, 16, now))
    answer = call(server.build(route, namer=named), "route_taken", minutes=30)
    assert answer["km"] == 5.8
    assert (answer["start"]["longitude"], answer["end"]["longitude"]) == (9.0, 9.1)
    assert answer["said"] == "Du har kjørt omtrent 5.8 kilometer på 10 minutter, fra Skuggevik til Skuggevik."


def test_a_reading_is_kept_for_kept_days_and_no_longer(route):
    old = time.time() - (KEPT_DAYS + 1) * 86400
    route.add(geo.Fix(58.6, 9.0, at=old))
    route.add(geo.Fix(58.6, 9.0, at=time.time()))
    assert len(route.since(0)) == 1


def test_slett_ruta_wipes_every_reading_at_once(route):
    route.add(geo.Fix(58.6, 9.0, at=time.time()))
    assert call(server.build(route, namer=named), "forget_route") == {
        "result": "Ruta er slettet: 1 målinger."
    }
    assert route.latest() is None


def test_a_place_is_looked_up_again_only_after_a_real_move():
    looked = []
    names = places.Names(lambda lat, _lon: looked.append(lat) or "Sted")
    names(geo.Fix(58.6, 9.0))
    names(geo.Fix(58.6001, 9.0))
    names(geo.Fix(58.61, 9.0))
    assert len(looked) == 2


def test_the_route_file_is_for_this_user_alone(tmp_path):
    Route(tmp_path / "state" / "route.sqlite")
    assert (tmp_path / "state" / "route.sqlite").stat().st_mode & 0o077 == 0


def test_where_says_how_old_the_latest_reading_is(tmp_path, capsys):
    store = tmp_path / "route.sqlite"
    Route(store).add(geo.Fix(58.6, 9.0, 90, 16, time.time() - 5))
    assert cli.main(["where", "--store", str(store)]) == 0
    assert capsys.readouterr().out.startswith("latest reading ")


def test_through_the_tailnet_only_roy_s_own_login_is_let_in(route):
    with TestClient(server.app(route, allowed="roy@example.com", namer=named)) as client:
        mine = client.post("/reading", json=SKUGGEVIK, headers={"Tailscale-User-Login": "Roy@Example.com"})
        theirs = client.post("/reading", json=SKUGGEVIK, headers={"Tailscale-User-Login": "eve@example.com"})
        local = client.post("/reading", json=SKUGGEVIK)
    assert (mine.status_code, theirs.status_code, local.status_code) == (200, 403, 200)
    assert len(route.since(0)) == 2


def test_a_call_needs_no_session_so_a_restart_breaks_nothing(route):
    """On 2026-10-10 a restart left Hermes with "Session not found" until it reconnected."""
    route.add(geo.Fix(58.6, 9.0, 90, 16, time.time()))
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    call_where = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "where_am_i", "arguments": {}},
    }
    with TestClient(server.app(route, namer=named), base_url="http://127.0.0.1:8770") as client:
        # A call with no session id, as a client that was connected before a restart sends.
        answer = client.post("/mcp", json=call_where, headers=headers)
    assert answer.status_code == 200
    assert answer.json()["result"]["structuredContent"]["place"] == "Skuggevik"


def test_the_phone_says_which_app_it_runs_and_where_its_sound_goes(route):
    mcp = server.build(route, namer=named)
    with TestClient(mcp.streamable_http_app()) as client:
        client.post(
            "/reading", json={**SKUGGEVIK, "app": "0.10", "sound": "bilens handsfree, som en samtale"}
        )
    phone = call(mcp, "where_am_i")["phone"]
    assert phone["app"] == "0.10"
    assert phone["sound"] == "bilens handsfree, som en samtale"


def test_a_silence_of_trip_pause_begins_a_new_drive(route):
    now = time.time()
    route.add(geo.Fix(58.5, 8.8, 0, 20, now - 3 * 3600))  # this morning's drive
    route.add(geo.Fix(58.51, 8.8, 0, 20, now - 3 * 3600 + 60))
    route.add(geo.Fix(58.6, 8.9, 0, 20, now - 120))  # the drive now, after a long silence
    route.add(geo.Fix(58.61, 8.9, 0, 20, now - 60))
    with TestClient(server.app(route, namer=named)) as client:
        line = client.get("/route.geojson").json()["geometry"]["coordinates"]
        everything = client.get("/route.geojson", params={"minutes": 600}).json()["geometry"]["coordinates"]
    assert line == [[8.9, 58.6], [8.9, 58.61]]
    assert len(everything) == 4


def test_pressing_follow_begins_a_new_drive(route):
    now = time.time()
    route.add(geo.Fix(58.5, 8.8, 0, 20, now - 120))
    with TestClient(server.app(route, namer=named)) as client:
        client.post("/trip")
        route.add(geo.Fix(58.6, 8.9, 0, 20, time.time() + 1))
        line = client.get("/route.geojson").json()["geometry"]["coordinates"]
    assert line == [[8.9, 58.6]]


def test_old_drives_are_listed_and_drawn_again(route):
    now = time.time()
    for i in range(5):
        route.add(geo.Fix(58.50 + i * 0.002, 8.8, 0, 20, now - 3 * 3600 + i * 60))
    for i in range(5):
        route.add(geo.Fix(58.60 + i * 0.002, 8.9, 0, 20, now - 600 + i * 60))
    with TestClient(server.app(route, namer=named)) as client:
        trips = client.get("/trips.json").json()["trips"]
        assert len(trips) == 2
        assert trips[0]["began"] > trips[1]["began"]  # newest first
        assert trips[1]["km"] > 0
        old = trips[1]
        line = client.get("/route.geojson", params={"began": old["began"], "ended": old["ended"]}).json()
    assert line["geometry"]["coordinates"][0] == [8.8, 58.5]
    assert len(line["geometry"]["coordinates"]) == 5


def test_the_map_can_ask_for_just_where_roy_is_now(route):
    route.add(geo.Fix(58.6, 8.9, 0, 20, time.time()))
    with TestClient(server.app(route, namer=named)) as client:
        now = client.get("/here.json").json()
    assert (now["known"], now["latitude"], now["longitude"]) == (True, 58.6, 8.9)


def test_a_reading_sent_late_keeps_the_time_it_was_measured(route):
    measured = time.time() - 5 * 3600  # held back on the phone through five hours without network
    with TestClient(server.app(route, namer=named)) as client:
        client.post("/reading", json={**SKUGGEVIK, "at": measured, "late": True})
        client.post("/reading", json={**SKUGGEVIK, "latitude": 58.7, "at": measured})  # not marked late
    kept = route.since(0)
    assert round(kept[0].at) == round(measured)
    assert kept[-1].at > measured + 4 * 3600  # an unmarked one that old is not believed
