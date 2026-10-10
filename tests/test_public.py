"""The tools as Claude on the web reaches them: signed in by the owner, and by no one else."""

import base64
import hashlib
import re
import sqlite3
import time
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from whereabouts import geo, public, server
from whereabouts.oauth import OAuthProvider
from whereabouts.store import Route

HOST = "h.ts.net"
PUBLIC = f"https://{HOST}/whereabouts"
SECRET = "correct horse battery staple"  # noqa: S105 — a test value
REDIRECT = "https://claude.ai/api/mcp/auth_callback"


def named(_fix):
    return "Skuggevik"


@pytest.fixture
def client():
    route = Route(None)
    route.add(geo.Fix(58.6, 9.0, 90, 16, time.time()))
    provider = OAuthProvider(sqlite3.connect(":memory:", check_same_thread=False), SECRET, PUBLIC)
    with TestClient(public.app(route, provider, PUBLIC, namer=named), base_url=f"https://{HOST}") as tested:
        yield tested


def sign_in(client, secret=SECRET):
    """Register, ask, consent and trade the code, as Claude on the web does. Returns the last response."""
    registered = client.post(
        "/register",
        json={"redirect_uris": [REDIRECT], "token_endpoint_auth_method": "none", "client_name": "Claude"},
    ).json()
    verifier = "v" * 64
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    asked = client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": registered["client_id"],
            "redirect_uri": REDIRECT,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "s",
        },
        follow_redirects=False,
    )
    consent = urlparse(asked.headers["location"])
    # The consent page is under the service's own path, not the shared host's root.
    assert consent.path == "/whereabouts/oauth/consent"
    request_id = parse_qs(consent.query)["request"][0]
    page = client.get("/oauth/consent", params={"request": request_id}).text
    assert f"action='{PUBLIC}/oauth/consent'" in page
    answered = client.post(
        "/oauth/consent",
        data={"request": request_id, "secret": secret, "action": "allow"},
        follow_redirects=False,
    )
    if answered.status_code != 302:
        return answered
    code = parse_qs(urlparse(answered.headers["location"]).query)["code"][0]
    return client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "client_id": registered["client_id"],
            "code_verifier": verifier,
        },
    )


CALL = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "where_am_i", "arguments": {}}}
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def test_signed_in_by_the_owner_claude_can_ask_where_roy_is(client):
    token = sign_in(client).json()["access_token"]
    answer = client.post("/mcp", json=CALL, headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"})
    assert answer.status_code == 200
    assert answer.json()["result"]["structuredContent"]["place"] == "Skuggevik"


def test_without_signing_in_nothing_is_answered_and_the_way_to_sign_in_is_named(client):
    answer = client.post("/mcp", json=CALL, headers=MCP_HEADERS)
    assert answer.status_code == 401
    # Funnel strips the path, so this lands on the resource-metadata mount, not claude-voice's root.
    assert (
        f"https://{HOST}/.well-known/oauth-protected-resource/whereabouts/mcp"
        in answer.headers["www-authenticate"]
    )


def test_the_wrong_secret_gets_no_code(client):
    assert sign_in(client, secret="guess").status_code == 401  # noqa: S106 — a wrong one, on purpose


def test_the_sign_in_is_described_under_the_service_s_own_path(client):
    meta = client.get("/").json()
    assert meta["issuer"].rstrip("/") == PUBLIC
    assert meta["authorization_endpoint"] == f"{PUBLIC}/authorize"
    assert "none" in meta["token_endpoint_auth_methods_supported"]


def test_any_path_on_the_resource_mount_says_where_to_sign_in():
    with TestClient(public.resource_metadata(PUBLIC)) as client:
        meta = client.get("/mcp").json()
    assert meta == {
        "resource": f"{PUBLIC}/mcp",
        "authorization_servers": [PUBLIC],
        "scopes_supported": ["whereabouts"],
        "bearer_methods_supported": ["header"],
    }


def test_the_login_code_is_shown_only_to_the_owner_s_own_tailnet_login():
    application = server.app(Route(None), allowed="roy@example.com", login_secret=SECRET, namer=named)
    with TestClient(application) as client:
        mine = client.get("/login-code", headers={"Tailscale-User-Login": "roy@example.com"})
        local = client.get("/login-code")
        theirs = client.get("/login-code", headers={"Tailscale-User-Login": "eve@example.com"})
    assert mine.status_code == 200
    assert SECRET in mine.text
    assert mine.headers["cache-control"] == "no-store"
    assert (local.status_code, theirs.status_code) == (403, 403)
    assert not re.search(SECRET, local.text + theirs.text)
