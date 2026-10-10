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
- **Answer over MCP**, so Hermes can ask when it needs to. The tools are below;
  a `tour` tool, for the next stop on a guided tour, comes later.
- **Show the route on a map** when asked.

## What it promises

- **A route is kept on this machine only, for 30 days.** Saying "slett ruta"
  wipes it at once. Roy chose this on 2026-10-10.
- **Nothing is sent anywhere unless something asks.** Hermes's model sees a
  position only in an answer to a question it asked.
- **No key, token or position is printed or committed.**

## Running it

It listens on this machine only, on port 8770: MCP at `/mcp`, readings in at
`/reading`, and the route at `/route.geojson` and on a map at `/map`.

```console
$ whereabouts serve --help
usage: whereabouts serve [-h] [--port PORT] [--store STORE]

options:
  -h, --help     show this help message and exit
  --port PORT    what port to listen on
  --store STORE  where the route is kept
```

`where` says how old the latest reading is, without saying where it was:

```console
$ whereabouts where --store /tmp/whereabouts-example/route.sqlite
no reading yet
```

Without `--store`, the route is kept in `~/.local/state/whereabouts/route.sqlite`,
readable by this user alone.

## The tools Hermes has

| Tool | What it answers |
|---|---|
| `where_am_i` | The place, the direction, the speed, and how old the reading is. |
| `whats_around` | Named things on one side: `venstre`, `høyre`, `foran` or `bak`. |
| `route_taken` | How far, from where to where, and how long, over the last minutes. |
| `forget_route` | Wipes the whole route, as "slett ruta" asks. |

## Status

The first version: readings in, the four tools, and the map. The voice bridge
still follows the position itself during a call. Passing readings here, and
telling Hermes about this server, come next.

## Licence

Apache-2.0.
