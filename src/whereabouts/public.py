"""The service as Claude on the web reaches it: the same tools, behind the owner's sign-in.

Published through Tailscale Funnel under a path on a host claude-voice also
uses, as `https://<host>/whereabouts`. Funnel strips that path before a request
arrives, so two things a client looks for at the root of the host are mounted
on their own:

- `/.well-known/oauth-protected-resource/whereabouts`, which says where the
  sign-in is, answered by `resource_metadata` on a port of its own;
- `/.well-known/oauth-authorization-server/whereabouts`, which describes the
  sign-in, arriving here as `/`.

Readings in, the route as a line and the map are not here at all: they stay on
the tailnet-only service.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from mcp.server import MCPServer
from mcp.server.auth.routes import build_metadata
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.responses import JSONResponse, Response

from whereabouts import places
from whereabouts.oauth import SCOPE, OAuthProvider, PublicClientMetadata
from whereabouts.server import INSTRUCTIONS, tools

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.types import ASGIApp, Receive, Scope, Send

    from whereabouts import geo
    from whereabouts.store import Route


def settings(public_url: str) -> AuthSettings:
    """The sign-in as the MCP library wants it described, for an issuer under a path."""
    return AuthSettings(
        issuer_url=AnyHttpUrl(public_url),
        resource_server_url=AnyHttpUrl(f"{public_url}/mcp"),
        client_registration_options=ClientRegistrationOptions(
            enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]
        ),
        required_scopes=[SCOPE],
        revocation_options=RevocationOptions(enabled=True),
        validate_token_resource=False,
    )


def app(
    route: Route,
    provider: OAuthProvider,
    public_url: str,
    *,
    nearby: geo.Fetch | None = None,
    namer: places.Namer | None = None,
) -> ASGIApp:
    """The tools behind the sign-in, with the consent page and the sign-in's own description."""
    auth = settings(public_url)
    registration = auth.client_registration_options or ClientRegistrationOptions()
    revocation = auth.revocation_options or RevocationOptions()
    mcp = MCPServer("whereabouts", instructions=INSTRUCTIONS, auth_server_provider=provider, auth=auth)
    for tool in tools(route, namer or places.Names(), nearby):
        mcp.tool()(tool)
    mcp.custom_route("/oauth/consent", methods=["GET"])(provider.consent_page)
    mcp.custom_route("/oauth/consent", methods=["POST"])(provider.consent_submit)

    async def described(_: Request) -> Response:
        """What a client finds at /.well-known/oauth-authorization-server/whereabouts."""
        meta = build_metadata(
            auth.issuer_url,
            auth.service_documentation_url,
            registration,
            revocation,
        ).model_dump(mode="json", exclude_none=True)
        methods = meta.setdefault("token_endpoint_auth_methods_supported", [])
        if "none" not in methods:
            methods.append("none")
        return JSONResponse(meta)

    mcp.custom_route("/", methods=["GET"])(described)
    host = urlparse(public_url).netloc
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", host],
        allowed_origins=[f"https://{host}", "http://127.0.0.1:*", "http://localhost:*"],
    )
    built = mcp.streamable_http_app(transport_security=security, stateless_http=True, json_response=True)
    return PublicClientMetadata(built)


class ResourceMetadata:
    """Says, for any path, where the tools are and where to sign in: RFC 9728's document."""

    def __init__(self, public_url: str) -> None:
        """Describe the tools under `public_url`."""
        self.body = json.dumps(
            {
                "resource": f"{public_url}/mcp",
                "authorization_servers": [public_url],
                "scopes_supported": [SCOPE],
                "bearer_methods_supported": ["header"],
            }
        ).encode()

    async def __call__(self, scope: Scope, _receive: Receive, send: Send) -> None:
        """Answer every request with the same document."""
        if scope["type"] == "lifespan":
            message = await _receive()
            while message["type"] != "lifespan.shutdown":
                await send({"type": "lifespan.startup.complete"})
                message = await _receive()
            await send({"type": "lifespan.shutdown.complete"})
            return
        if scope["type"] != "http":
            return
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(self.body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": self.body})


def resource_metadata(public_url: str) -> ResourceMetadata:
    """The app the protected-resource mount points at."""
    return ResourceMetadata(public_url)


def login_code_page(secret: str, allowed: str) -> Any:  # noqa: ANN401 — a Starlette endpoint
    """The login secret, shown only to the owner over the tailnet, never to this machine or the internet.

    The secret is typed once on the consent page when Claude on the web first
    connects. It is never printed, logged or sent in a chat; Tailscale's own
    login header is what proves the owner is asking.
    """

    async def page(request: Request) -> Response:
        login = request.headers.get("tailscale-user-login", "").casefold()
        # RULE: the login code is shown only to the owner's own tailnet login
        if not login or login != allowed.casefold() or not secret:
            return JSONResponse({"error": "not yours"}, 403)
        return Response(
            "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<title>Innloggingskode</title><body style='font:20px system-ui;margin:2rem'>"
            "<p>Skriv denne når Claude spør, første gang:</p>"
            f"<p style='font:28px ui-monospace;user-select:all'>{secret}</p>",
            media_type="text/html",
            headers={"Cache-Control": "no-store"},
        )

    return page
