# ADR-W-001: A service of its own, on this machine, answering over MCP

## Status

Accepted, by Roy Kollen Svendsen, 2026-10-10.

## Context

Roy asked on 2026-10-10 for several things while he drives:

- Hermes should know where he is, which way he is going and how fast.
- "What is on the left?" should be answered.
- A guided tour should speak as he reaches a place.
- His route should be shown on a map in the app.

The voice bridge in
[voice-integration](https://github.com/roykollensvendsen/voice-integration)
already followed the phone during a call, but kept only the latest reading in
memory, and only it could ask.

## Options considered

**Keep it in the voice bridge.** Not taken. The bridge's job is the voice, and
Hermes and the Claude sessions would still have no way to ask on their own.

**Send the position with every request to Hermes.** Not taken. Hermes's model
would see where Roy is on turns that have nothing to do with it, and it could
not ask about the route.

**A service of its own, answering over MCP.** Taken. Hermes already uses MCP
for claude-voice, so this is the same pattern.

## Decision

whereabouts is its own repository and its own service. It listens on this
machine only. Readings come in over plain HTTP from the voice bridge. Hermes,
and anything else with an MCP client, asks four tools: `where_am_i`,
`whats_around`, `route_taken` and `forget_route`. The route is drawn at `/map`.

## Consequences

Anything that needs to know where Roy is asks one place, and it can ask when it
needs to. The cost is a second service to keep running and keep in step with
the bridge. A change to the reading's shape is made on both sides, and tested
together. Hermes has to be told about the server, which is a change to its
setup that Roy approves.

## Related

[`docs/location-proposal.md`](https://github.com/roykollensvendsen/voice-integration/blob/main/docs/location-proposal.md)
in voice-integration; [ADR-W-002](ADR-W-002-the-route-is-kept-thirty-days-on-this-machine.md).
