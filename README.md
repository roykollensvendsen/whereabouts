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

Each answer has a `said` sentence, to be spoken, and the figures behind it:
latitude, longitude, heading in degrees, speed in metres a second, and when it
was measured. The figures are for Hermes to work with, such as distances, map
lookups or what lies ahead. Its instructions say never to read them aloud.

| Tool | What it answers |
|---|---|
| `where_am_i` | The place, the direction, the speed, and how old the reading is; and the figures behind them. |
| `whats_around` | Named things on one side: `venstre`, `høyre`, `foran` or `bak`. |
| `route_taken` | How far, from where to where, and how long, over the last minutes. |
| `forget_route` | Wipes the whole route, as "slett ruta" asks. |
| `sights_near` | Named sights near a point, with their Wikipedia article, worth describing. |
| `describe_places` | Keeps places Hermes has written about, for the phone to tell of as Roy passes. |
| `described_near` | The places already described near a point, so none is described twice. |
| `sights_along` | Everything with a name along the road between two points: villages, farms, water, roads and sights. |
| `sights_on_route_taken` | What has a name along the route driven in the last hours and is not described yet. |
| `add_local_news` | Fresh local news about a place, told for some days and then gone. |
| `leave_note` | Leaves what Roy says where he is now, read back to him the next time he passes. |
| `forget_described` | Stops telling of a place, or of a note by a few of its words. |

How Hermes writes about places is in the skill
[`hermes/skills/stedsguide`](hermes/skills/stedsguide/SKILL.md), linked into
Hermes's skills folder; it is improved from Roy's feedback and from going
through his drives afterwards.

What Hermes writes about a place is kept until forgotten, so the phone tells
of it every time Roy drives past, and there are more such places as time goes
on. The phone fetches those near Roy from `/described`; why it works this way is
[ADR-W-004](decisions/ADR-W-004-places-are-described-here-and-told-by-the-phone.md).

## From Claude on the web

`serve-public` runs the same tools for Claude on the web and in the Claude app,
behind a sign-in that only the owner can complete:

```console
$ whereabouts serve-public --help
usage: whereabouts serve-public [-h] [--port PORT] [--meta-port META_PORT]
                                --public-url PUBLIC_URL [--store STORE]

options:
  -h, --help            show this help message and exit
  --port PORT           what port the tools listen on
  --meta-port META_PORT
                        what port says where to sign in
  --public-url PUBLIC_URL
                        the address Claude reaches, with its path
  --store STORE         where the route is kept
```

It is published through Tailscale Funnel under a path, `/whereabouts`, on the
same host as claude-voice. Funnel strips that path, so three mounts are needed:
- `/whereabouts` goes to `--port`;
- `/.well-known/oauth-authorization-server/whereabouts` goes to `--port`, where
  it arrives as `/`;
- `/.well-known/oauth-protected-resource/whereabouts` goes to `--meta-port`.

The first time Claude connects, it opens a consent page that asks for the
login secret. The owner finds it at `/login-code` on the tailnet-only service,
and only from his own tailnet login. The secret is never printed or sent in a
chat. Readings in, the route as a line and the map are not published.

## From the phone

The app in [`android/`](android/README.md) sends readings straight here, only
when something has changed. The service is reached over the tailnet, served by
`tailscale serve` on HTTPS port 10001. A request that comes through the tailnet
is let in only when its tailnet login is the one in
`WHEREABOUTS_ALLOWED_LOGIN`. A request from this machine carries no login, and
is let in. [`deploy/whereabouts.service`](deploy/whereabouts.service) keeps it
running.

## Status

Readings come in from the phone app, the four tools answer, and the map draws the
route. Telling Hermes about this server is next, and needs Roy's yes, since it
changes Hermes's setup.

## Licence

Apache-2.0.
