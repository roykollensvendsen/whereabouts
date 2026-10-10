"""Command line for whereabouts: run the service, or say where the latest reading puts Roy."""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

from whereabouts import geo
from whereabouts.store import Route, default_path

#: Every verb this command has. The documentation test requires each one to
#: appear in a worked example, so a verb cannot be added without one.
COMMANDS: tuple[str, ...] = ("serve", "where")

#: Where the service listens: this machine only.
HOST = "127.0.0.1"
PORT = 8770


def _route(args: argparse.Namespace) -> Route:
    return Route(pathlib.Path(args.store) if args.store else default_path())


def _serve(args: argparse.Namespace) -> int:
    import uvicorn  # noqa: PLC0415 — only the service needs the web server

    from whereabouts import server  # noqa: PLC0415 — nor the MCP library

    uvicorn.run(server.app(_route(args)), host=HOST, port=args.port, log_level="info")
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
    where = verbs.add_parser("where", help="say how old the latest reading is, and the way it was going")
    where.add_argument("--store", default="", help="where the route is kept")
    args = parser.parse_args(argv)
    return {"serve": _serve, "where": _where}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
