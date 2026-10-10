"""The service: readings in over HTTP, answers out over MCP, and the route on a map.

It listens on this machine only. The voice bridge passes on each reading the
phone sends it; Hermes, and anything else with an MCP client, asks the tools
below when it needs to know where Roy is.
"""

from __future__ import annotations

import itertools
import json
import time
from typing import TYPE_CHECKING, Any

from mcp.server import MCPServer
from starlette.responses import HTMLResponse, JSONResponse, Response

from whereabouts import described, geo, places

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.types import ASGIApp, Receive, Scope, Send

    from whereabouts.store import Route

    #: Finds the road between two points, as latitude and longitude pairs.
    Router = Callable[[tuple[float, float], tuple[float, float]], list[tuple[float, float]]]

INSTRUCTIONS = (
    "Where Roy is, which way he is going, how fast, what is around him, and the route he has "
    "taken in the last 30 days, from his phone. Ask where_am_i before saying where he is. "
    "Each answer has a `said` sentence to speak, and the numbers behind it: latitude, longitude, "
    "heading in degrees, speed in metres a second, and when it was measured. Use the numbers for "
    "work, such as distances, map lookups or what lies ahead; never read them aloud, and never "
    "pass them anywhere he has not asked for. His phone tells him of places as he drives past them, "
    "from what is written with describe_places; what is written is kept, so the same places are told "
    "of every time he passes. Find what is worth telling with sights_near, check described_near so "
    "nothing is described twice, and write each text yourself, in Norwegian, two or three sentences "
    "to be heard while driving past."
)

#: The longest span `route` describes, in minutes: thirty days.
LONGEST_ROUTE_MINUTES = 30 * 24 * 60


def build(
    route: Route,
    *,
    nearby: geo.Fetch | None = None,
    namer: places.Namer | None = None,
    router: Router | None = None,
) -> MCPServer:
    """The MCP server and its routes, over one route store."""
    mcp = MCPServer("whereabouts", instructions=INSTRUCTIONS)
    name = namer or places.Names()
    for tool in tools(route, name, nearby, router):
        mcp.tool()(tool)
    for path, method, handler in routes(route):
        mcp.custom_route(path, methods=[method])(handler)
    return mcp


def tools(
    route: Route, name: places.Namer, nearby: geo.Fetch | None, router: Router | None = None
) -> list[Callable[..., Any]]:
    """What Hermes can ask, each answering in words a person can hear."""

    def where_am_i() -> dict[str, Any]:
        """Where Roy is now: the place, which way and how fast he is going, and how old the reading is."""
        fix = route.latest()
        if fix is None:
            return {"known": False, "said": "Jeg vet ikke hvor du er ennå."}
        place = name(fix)
        return {
            "known": True,
            "said": geo.described(fix, place, timed=True),
            "place": place,
            # Roy, 2026-10-10: the numbers too, to work with, not to read out.
            **numbers(fix),
            "direction": geo.compass(fix.heading) if fix.moving() and fix.heading is not None else None,
            "km_h": round((fix.speed or 0.0) * 3.6) if fix.speed is not None else None,
            "seconds_old": round(time.time() - fix.at),
        }

    def whats_around(side: str) -> str:
        """What is on one side of the way Roy is going: "venstre", "høyre", "foran" or "bak"."""
        if side not in geo.SIDES:
            return f"Si en av {', '.join(geo.SIDES)}."
        fix = route.latest()
        if fix is None or not fix.fresh():
            return "Jeg vet ikke hvor du er akkurat nå."
        return geo.on_the_side(fix, side, geo.nearby(fix, nearby))

    def route_taken(minutes: int = 60) -> dict[str, Any]:
        """The route over the last `minutes`: how far, from where to where, and how long it took."""
        taken = route.since(time.time() - max(1, min(minutes, LONGEST_ROUTE_MINUTES)) * 60)
        if len(taken) < 2:  # noqa: PLR2004 — a route needs two readings
            return {"readings": len(taken), "said": "Jeg har ingen rute fra den tiden."}
        metres = sum(geo.metres_between(a, b.latitude, b.longitude) for a, b in itertools.pairwise(taken))
        km, took = round(metres / 1000, 1), round((taken[-1].at - taken[0].at) / 60)
        start, end = name(taken[0]) or "et ukjent sted", name(taken[-1]) or "et ukjent sted"
        return {
            "readings": len(taken),
            "km": km,
            "minutes": took,
            "start": numbers(taken[0]),
            "end": numbers(taken[-1]),
            "said": f"Du har kjørt omtrent {km} kilometer på {took} minutter, fra {start} til {end}.",
        }

    def forget_route() -> str:
        """Wipe the whole route at once, as Roy asks with "slett ruta"."""
        return f"Ruta er slettet: {route.forget()} målinger."

    return [where_am_i, whats_around, route_taken, forget_route, *telling_tools(route, nearby, router)]


def _length(road: list[tuple[float, float]]) -> float:
    return sum(
        geo.metres_between(geo.Fix(a[0], a[1], None, None, 0.0), *b) for a, b in itertools.pairwise(road)
    )


def telling_tools(
    route: Route, nearby: geo.Fetch | None, router: Router | None = None
) -> list[Callable[..., Any]]:
    """Describing places, which his phone then tells of as he passes them."""
    kept = described.Places(route)

    def describe_places(places: list[dict[str, Any]]) -> dict[str, Any]:
        """Describe places for his phone to tell of as he passes, now and every time after.

        Each place is {"name", "latitude", "longitude", "said", "radius_m"}. Write
        `said` yourself: Norwegian, two or three sentences about what he is
        passing and why it is worth knowing, never its coordinates. `radius_m`
        is how close counts (default 150; a view or a landmark seen from afar
        wants more). A place already described, by name nearby or at the same
        spot, is rewritten rather than added twice.
        """
        try:
            done = kept.add(places)
        except ValueError as wrong:
            return {"added": 0, "updated": 0, "said": str(wrong)}
        return {**done, "said": f"{done['added']} nye steder, {done['updated']} skrevet om."}

    def described_near(latitude: float, longitude: float, km: float = 5.0) -> list[dict[str, Any]]:
        """The places already described within `km` (at most 50) of a point, nearest first."""
        return kept.near(latitude, longitude, min(max(km, 0.1), 50.0) * 1000)

    def leave_note(said: str, radius_m: float = described.DEFAULT_RADIUS_M) -> str:
        """Leave what Roy says here, by the road, to be read back to him the next time he passes.

        For "legg igjen en melding her: ...". It is placed where he is now, and
        told every time he passes until he asks to forget it, by the name
        "Melding" or by its words.
        """
        fix = route.latest()
        if fix is None or not fix.fresh():
            return "Jeg vet ikke hvor du er akkurat nå, så meldingen ble ikke lagt igjen."
        words = said.strip()
        if not words:
            return "Hva skal meldingen si?"
        note = {
            "name": f"Melding {time.strftime('%d.%m.%Y')}",
            "latitude": fix.latitude,
            "longitude": fix.longitude,
            "radius_m": radius_m,
            "said": f"En melding du la igjen her: {words}",
        }
        kept.add([note], kind=described.NOTE)
        return "Meldingen er lagt igjen her. Du får den lest opp neste gang du kjører forbi."

    def forget_described(name: str) -> str:
        """Stop telling of a place or a note: forget every one by this name, or whose words hold it."""
        return f"Glemt: {kept.forget(name)} steder."

    return [describe_places, described_near, leave_note, forget_described, *finding_tools(nearby, router)]


def finding_tools(nearby: geo.Fetch | None, router: Router | None) -> list[Callable[..., Any]]:
    """Finding what is worth describing, around a point or along a road."""
    router = router or geo.road_between

    def sights_near(latitude: float, longitude: float, km: float = 2.0) -> list[dict[str, Any]]:
        """Named sights within `km` (at most 5) of a point, worth describing.

        Each has its name, kind, where it is, and its Wikipedia article when
        OpenStreetMap names one, to read before writing what is said.
        """
        return geo.sights(latitude, longitude, min(max(km, 0.2), 5.0) * 1000, nearby)

    def sights_along(
        from_latitude: float, from_longitude: float, to_latitude: float, to_longitude: float
    ) -> dict[str, Any]:
        """What has a name along the road between two points, in the order it is passed.

        Villages, farms, lakes, rivers, bridges, roads and sights within a few
        hundred metres of the road, each with where it is and its Wikipedia
        article when there is one. Describe them with describe_places.
        """
        # The public road router is sent only the two ends, nothing about where Roy is.
        road = router((from_latitude, from_longitude), (to_latitude, to_longitude))
        if not road:
            return {"found": [], "said": "Fant ingen vei mellom de to stedene."}
        found = geo.sights_along(road, nearby)
        return {
            "km": round(_length(road) / 1000, 1),
            "found": found,
            "said": f"{len(found)} navn langs veien.",
        }

    return [sights_near, sights_along]


def numbers(fix: geo.Fix) -> dict[str, Any]:
    """A reading's figures, for a tool to work with; `said` is what is spoken."""
    return {
        "latitude": round(fix.latitude, 6),
        "longitude": round(fix.longitude, 6),
        "heading_degrees": None if fix.heading is None else round(fix.heading, 1),
        "speed_m_s": None if fix.speed is None else round(fix.speed, 2),
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(fix.at)),
    }


def routes(route: Route) -> list[tuple[str, str, Callable[[Request], Awaitable[Response]]]]:
    """The plain web routes: readings in, and the route out as a line and a map."""

    async def reading(request: Request) -> Response:
        """Keep one reading from the phone."""
        try:
            fix = geo.fix_from(json.loads(await request.body() or b"{}"))
        except (ValueError, TypeError, AttributeError):
            return JSONResponse({"error": "a reading is latitude and longitude, with heading and speed"}, 400)
        route.add(fix)
        return JSONResponse({"kept": True})

    async def route_json(request: Request) -> Response:
        """The route over the last `minutes` (default a day), as a line a map can draw."""
        minutes = int(request.query_params.get("minutes", "1440"))
        taken = route.since(time.time() - max(1, min(minutes, LONGEST_ROUTE_MINUTES)) * 60)
        line = [[fix.longitude, fix.latitude] for fix in taken]
        geometry = {"type": "LineString", "coordinates": line}
        return JSONResponse({"type": "Feature", "geometry": geometry, "properties": {"readings": len(line)}})

    async def route_map(_: Request) -> Response:
        """The route on a map, with where Roy is now."""
        return HTMLResponse(MAP)

    async def described_json(request: Request) -> Response:
        """The places described within `km` (default 30, at most 100) of a point, for the phone."""
        try:
            latitude = float(request.query_params["latitude"])
            longitude = float(request.query_params["longitude"])
            km = min(max(float(request.query_params.get("km", "30")), 0.1), 100.0)
        except (KeyError, ValueError):
            return JSONResponse({"error": "ask with latitude, longitude and km"}, 400)
        kept = described.Places(route)
        return JSONResponse({"version": kept.version(), "places": kept.near(latitude, longitude, km * 1000)})

    return [
        ("/reading", "POST", reading),
        ("/route.geojson", "GET", route_json),
        ("/map", "GET", route_map),
        ("/described", "GET", described_json),
    ]


#: The header Tailscale's `serve` adds, naming the tailnet user who asked. It
#: strips any copy the caller sent, so it can be trusted when it is there.
WHO = "tailscale-user-login"


def app(route: Route, allowed: str = "", login_secret: str = "", **kwargs: Any) -> Starlette:  # noqa: ANN401 — passed through to build
    """The web application: MCP at /mcp, and the reading, route and map routes beside it.

    `allowed` is the one tailnet login that may reach it from the phone. A
    request with no login came from this machine, where only Roy's own programs
    run, and is let through.
    """
    # Stateless: each call stands alone, so Hermes's connection outlives a
    # restart of this service. On 2026-10-10 a restart left it with "Session
    # not found" until it reconnected.
    built = build(route, **kwargs).streamable_http_app(stateless_http=True, json_response=True)
    # The code for signing Claude on the web in, for the owner's eyes only.
    from whereabouts.public import login_code_page  # noqa: PLC0415 — public imports this module

    built.add_route("/login-code", login_code_page(login_secret, allowed), methods=["GET"])
    built.add_middleware(OnlyRoy, allowed=allowed)
    return built


class OnlyRoy:
    """Turns away a request that came through the tailnet from anyone but `allowed`."""

    def __init__(self, inner: ASGIApp, allowed: str) -> None:
        """Wrap `inner`, letting `allowed` through from the tailnet."""
        self.inner = inner
        self.allowed = allowed.casefold()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Answer 403 to a tailnet login that is not Roy's, and pass everything else on."""
        if scope["type"] == "http":
            headers = {key.decode().casefold(): value.decode() for key, value in scope["headers"]}
            login = headers.get(WHO, "").casefold()
            # RULE: through the tailnet, only Roy's own login is let in
            if login and login != self.allowed:
                await JSONResponse({"error": "not yours"}, 403)(scope, receive, send)
                return
        await self.inner(scope, receive, send)


MAP = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ruta</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html, body, #map { height: 100%; margin: 0; }</style>
<div id="map"></div>
<script>
  const map = L.map("map");
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "&copy; OpenStreetMap",
  }).addTo(map);
  let drawn = null, here = null;
  async function draw() {
    const minutes = new URLSearchParams(location.search).get("minutes") ?? "1440";
    const route = await fetch(`route.geojson?minutes=${minutes}`).then((r) => r.json());
    const points = route.geometry.coordinates.map(([lon, lat]) => [lat, lon]);
    if (!points.length) { map.setView([59.9, 10.75], 5); return; }
    drawn?.remove(); here?.remove();
    drawn = L.polyline(points, { weight: 5 }).addTo(map);
    here = L.circleMarker(points.at(-1), { radius: 8 }).addTo(map);
    if (!draw.fitted) { map.fitBounds(drawn.getBounds(), { maxZoom: 16 }); draw.fitted = true; }
  }
  draw();
  setInterval(draw, 10_000);
</script>
"""
