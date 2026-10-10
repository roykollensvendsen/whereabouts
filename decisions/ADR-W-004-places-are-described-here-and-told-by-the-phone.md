# ADR-W-004: Places are described here, kept, and told by the phone as Roy passes

## Status

Accepted, by Roy Kollen Svendsen, 2026-10-10: "Jeg vil at Hermes skriver dem
selv", and that what Hermes describes is kept, so the same places are told of
next time and there are more of them along the roads he drives.

## Context

Roy wants to drive and hear, hands free, what he is passing. Three places could
hold it: the voice (voice-integration), this service with its phone app, or a
new app of its own. And a tour could be planned once and thrown away, or what
is written could be kept.

## Options considered

**In the voice.** Not taken: telling has to work without a call, and without
paying for a voice model, and the voice app only knows where Roy is during a
call.

**A new app.** Not taken for now: it would need a second location service in
the background, a second permission, a second fixed notification and twice the
GPS for the same readings.

**One planned tour at a time.** Not taken: what Hermes wrote would be lost
when the next tour was planned.

**A growing register here, told by the phone that already follows him.** Taken.

## Decision

The service keeps every place Hermes describes, beside the route: where it is,
how close counts, and what is said. Hermes adds to it with `describe_places`,
finds candidates with `sights_near` around a point or `sights_along` the road
between two points, and checks `described_near` first; a place
described again by the same name nearby, or at the same spot, is rewritten, not
added twice. Hermes writes the text himself, in Norwegian; Roy does not approve
it first. `forget_described` removes a place.

Roy can also leave a note by voice: `leave_note` keeps what he says where he
is at that moment, and it is told back to him every time he passes, until he
asks to forget it. A note is never merged with a place or with another note.

Each night Hermes looks at the route driven that day with
`sights_on_route_taken`, describes what has a name along it and is not
described yet, and adds fresh local news about those places with
`add_local_news` (Roy, 2026-10-10: "fint å få oppdaterte nyheter som er
knyttet til spesifikke lokale steder"). News is told for a few days, at most
thirty, and then fades on its own. To find what lies along the route, the map
service is asked about boxes around it, never the route itself.

The phone app fetches the places near Roy from `/described` and decides on its
own, on every GPS reading, when one is near enough. It tells of each place once
per pass with Android's own speech, and waits while another app, such as the
voice, holds the sound. Coordinates are never read aloud.

## Consequences

Places are told of on every drive past them, in a tunnel or a dead zone once
fetched, at no running cost, and anything that reaches the tools can add to
them: Hermes, the voice, or Claude on the web.

Unlike the route, described places are kept until forgotten, not thirty days,
and "slett ruta" does not remove them. They are public sights rather than
readings, but where they cluster says which roads Roy drives. The text is
Hermes's own and may be wrong; Roy chose that over approving each place.

The code is kept apart, `described.py` here and `Telling.kt` on the phone, so
it can move to an app of its own if [`deferred.md`](deferred.md) says it should.

## Related

[ADR-W-001](ADR-W-001-a-service-of-its-own-on-this-machine-answering-over-mcp.md),
[ADR-W-002](ADR-W-002-the-route-is-kept-thirty-days-on-this-machine.md).
