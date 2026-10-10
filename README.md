# whereabouts

Where Roy is, where he has been, and what is around him, for anything that
asks: Hermes, the voice bridge, and Claude Code sessions.

## Why it is its own service

The voice ([voice-integration](https://github.com/roykollensvendsen/voice-integration))
first asked the phone for a position once per call, and later followed it during
a call. Roy then asked for more, on 2026-10-10:

- Hermes should know where he is and which way he is going while he drives.
- "What is on the left?" should be answered.
- A guided tour should speak as he reaches each place.
- His route should be kept and shown on a map when he asks.

That is one job, and several things need it, so it lives here. The proposal it
comes from is
[`docs/location-proposal.md`](https://github.com/roykollensvendsen/voice-integration/blob/main/docs/location-proposal.md)
in voice-integration.

## What it will do

- **Take readings from the phone.** Position, direction, speed and time, every
  few seconds, over the tailnet only.
- **Answer over MCP**, so Hermes can ask when it needs to:
  - `where_am_i`: the place, direction, speed and how old the reading is.
  - `whats_around`: named things on one side of the way he is going.
  - `route`: where he has been, over a time span.
  - `tour`: the next stop on a guided tour, and what to say there.
- **Show the route on a map** when asked.

## What it promises

- **A route is kept on this machine only, for 30 days.** Saying "slett ruta"
  wipes it at once. Roy chose this on 2026-10-10.
- **Nothing is sent anywhere unless something asks.** Hermes's model sees a
  position only in an answer to a question it asked.
- **No key, token or position is printed or committed.**

## Status

Nothing is built yet. The voice bridge's own first step, following the
position during a call, is live in voice-integration, and moves here as this
service grows.

## Licence

Apache-2.0.
