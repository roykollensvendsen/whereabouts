"""Command line for whereabouts: run the service, or say where the latest reading puts Roy."""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time

from whereabouts import geo
from whereabouts.store import Route, default_path

#: Every verb this command has. The documentation test requires each one to
#: appear in a worked example, so a verb cannot be added without one.
COMMANDS: tuple[str, ...] = ("serve", "serve-public", "where")

#: Where the service listens: this machine only.
HOST = "127.0.0.1"
PORT = 8770


def _route(args: argparse.Namespace) -> Route:
    return Route(pathlib.Path(args.store) if args.store else default_path())


def _serve(args: argparse.Namespace) -> int:
    import uvicorn  # noqa: PLC0415 — only the service needs the web server

    from whereabouts import server  # noqa: PLC0415 — nor the MCP library

    allowed = os.environ.get("WHEREABOUTS_ALLOWED_LOGIN", "")
    secret = os.environ.get("WHEREABOUTS_LOGIN_SECRET", "")
    application = server.app(_route(args), allowed=allowed, login_secret=secret)
    uvicorn.run(application, host=HOST, port=args.port, log_level="info")
    return 0


def _serve_public(args: argparse.Namespace) -> int:
    import asyncio  # noqa: PLC0415 — only the public service runs two servers
    import sqlite3  # noqa: PLC0415

    import uvicorn  # noqa: PLC0415

    from whereabouts import oauth, public  # noqa: PLC0415

    secret = os.environ.get("WHEREABOUTS_LOGIN_SECRET", "")
    if not secret:
        sys.stderr.write("WHEREABOUTS_LOGIN_SECRET is not set; nobody could sign in\n")
        return 1
    tokens = default_path().with_name("oauth.sqlite")
    tokens.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(str(tokens), check_same_thread=False)
    tokens.chmod(0o600)
    provider = oauth.OAuthProvider(db, secret, args.public_url)
    tools = public.app(_route(args), provider, args.public_url)
    meta = public.resource_metadata(args.public_url)
    servers = [
        uvicorn.Server(uvicorn.Config(tools, host=HOST, port=args.port, log_level="info")),
        uvicorn.Server(uvicorn.Config(meta, host=HOST, port=args.meta_port, log_level="warning")),
    ]

    async def both() -> None:
        await asyncio.gather(*(each.serve() for each in servers))

    asyncio.run(both())
    return 0


def _where(args: argparse.Namespace) -> int:
    fix = _route(args).latest()
    if fix is None:
        sys.stdout.write("no reading yet\n")
        return 0
    age = round(time.time() - fix.at)
    moving = f", going {geo.compass(fix.heading)}" if fix.moving() and fix.heading is not None else ""
    sys.stdout.write(f"latest reading {age} s ago{moving}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch. Returns a process exit code."""
    parser = argparse.ArgumentParser(prog="whereabouts", description=__doc__)
    verbs = parser.add_subparsers(dest="command", required=True)
    serve = verbs.add_parser("serve", help="run the service on this machine")
    serve.add_argument("--port", type=int, default=PORT, help="what port to listen on")
    serve.add_argument("--store", default="", help="where the route is kept")
    published = verbs.add_parser("serve-public", help="run the tools for Claude on the web, behind sign-in")
    published.add_argument("--port", type=int, default=PORT + 1, help="what port the tools listen on")
    published.add_argument("--meta-port", type=int, default=PORT + 2, help="what port says where to sign in")
    published.add_argument("--public-url", required=True, help="the address Claude reaches, with its path")
    published.add_argument("--store", default="", help="where the route is kept")
    where = verbs.add_parser("where", help="say how old the latest reading is, and the way it was going")
    where.add_argument("--store", default="", help="where the route is kept")
    args = parser.parse_args(argv)
    return {"serve": _serve, "serve-public": _serve_public, "where": _where}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
