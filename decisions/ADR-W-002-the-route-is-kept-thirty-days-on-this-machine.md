# ADR-W-002: The route is kept thirty days on this machine, and wiped on request

## Status

Accepted, by Roy Kollen Svendsen, 2026-10-10 ("30 dager er greit").

## Context

Until now a position was never written down. The voice bridge held it in
memory, and forgot it on restart. A route on a map has to be written down.

## Options considered

**Not at all.** Not taken: Hermes would still know where Roy is now, but there
would be no route and no map.

**Only until the call ends.** Not taken: a route from earlier in the day could
not be shown.

**Thirty days, on this machine only.** Taken.

## Decision

Every reading is kept in one SQLite file on this machine. The file and its
folder can be read by this user alone. A reading older than thirty days is
deleted whenever a new one arrives. Saying "slett ruta" calls `forget_route`,
which deletes every reading at once.

## Consequences

The route can be drawn and described for a month back. The cost is a file that
says where Roy has been. It stays on this machine and is never committed, but
anyone with this user's access could read it. A month is long enough for "where
did we drive last weekend", and short enough that the file never becomes a
history of a year.

## Related

[ADR-W-001](ADR-W-001-a-service-of-its-own-on-this-machine-answering-over-mcp.md).
