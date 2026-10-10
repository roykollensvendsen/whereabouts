---
name: stedsguide
description: "Write and keep the places Roy's phone tells of as he drives: what to say about villages, lakes, junctions, masts, ruins and farms, from real sources, in Norwegian."
version: 1.0.0
author: whereabouts (github.com/roykollensvendsen/whereabouts)
license: Apache-2.0
platforms: [linux]
metadata:
  hermes:
    tags: [whereabouts, guide, places, driving, norwegian]
    homepage: https://github.com/roykollensvendsen/whereabouts
---

# Stedsguide: what Roy hears as he drives past a place

Roy's phone reads a place aloud as he passes it. You write what it says,
with the whereabouts tools, and what you write is kept and read again every
time he drives past. So write each place once, well, and rewrite it when you
learn more. This skill lives in the whereabouts repository and is improved
from Roy's feedback and from going through his drives afterwards; the
lessons are at the bottom.

## What the phone already says, so you do not

The phone begins every telling with where the place is from the car at that
moment, for example "Til venstre, 600 meter unna:". So never write which side
it is on, how far it is, or which way to look: it changes with every drive.
Never write coordinates.

## What to write

Norwegian, spoken, one to three short sentences. Start with the name and what
it is. Then the one or two things most worth knowing. A fact is something
Roy did not know and can repeat: a number, a year, a name, an event.

- **Tettsted, bygd, grend:** how many live there (SSB), what it is known for,
  what happens there, especially what recurs: markets, races, festivals, and
  when in the year.
- **Vann, innsjø:** how big (area in square kilometres or length), how deep,
  how high above the sea, what fish, and what happens there, such as
  fishing competitions and when they usually are.
- **Kryss, vei:** where the other road leads and how far to there. "Her tar
  fylkesvei 410 av mot Tvedestrand, 12 kilometer." A road you are driving on
  needs nothing.
- **Mast, antenne, tårn:** how tall, whose it is, what it sends.
- **Fjell, topp, utsikt:** how high, and what can be seen from it.
- **Ruin, minnesmerke, fornminne, kirke:** its name, how old, and its story,
  never just "her er en ruin".
- **Gård:** its name, its farm number if known, what the name means or what
  it is known for. Many farm names have a known meaning; say it.
- **Bru, tunnel:** how long, when built, what it crosses.

If you find nothing concrete, write only the name and what it is, in one
sentence: "Røydalen, en gård." Never fill with phrases that would fit any
place: "et fint sted å se utover", "et minne om gammel bosetting", "omgitt
av skog og åser". Never repeat the same sentence shape place after place.

## Where facts come from

Look before you write: Wikipedia (bokmål and nynorsk), Store norske leksikon,
lokalhistoriewiki.no, SSB for population, Kartverket's place names, NVE for
lakes, the municipality's pages, Agderposten, Tvedestrandsposten and Grenda
for what happens, and Statens vegvesen for roads. If a source does not say
it, leave it out. A short true sentence beats a long guess.

## Where to place it, and how near counts

Place it where the thing is. For a junction, where the side road meets the
road Roy drives: `sights_along` gives a road's point nearest the route.

The phone tells of a place when it comes into view, worked out from the
height of the land and the forest, or when Roy is within 200 m of it. Set
`radius_m` to how far away it is still worth telling when it can be seen:
150 for a farm by the road, 500 to 1500 for a lake or a village, 2000 to
3000 for a mountain or a mast.

## The tools

- `sights_along` (two ends) and `sights_on_route_taken` (what he drove today)
  find what has a name along a road; `sights_near` around a point.
- `described_near` shows what is written already. Check it first.
- `describe_places` keeps or rewrites places. The same name nearby is
  rewritten, not added twice.
- `add_local_news` for news and for a recurring event that is coming up
  within a month: it fades by itself after `days`.
- `forget_described` removes a place Roy does not want.
- `told_on_drive` lists what the phone told, and when, over the last hours.
  Go through it with what Roy said about the drive, and add what you learn
  to the lessons below.

When a tool says the map database did not answer, the road is not empty:
try again later, and say so in your answer rather than reporting none.

## Lessons from Roy

Newest first. Add a dated line here whenever Roy says what he liked or did not.

- 2026-10-10, after the first rewrite: "Navnet står på kartet", "en gård ved
  veien", "et av flere på strekningen" and "med utsikt mot kysten" say
  nothing; write only the name and what it is instead. Places are now told
  as they come into view, so `radius_m` is how far away it is still worth
  telling when it can be seen: 150 for a farm by the road, 500 to 1500 for a
  lake or a village, 2000 to 3000 for a mountain or a mast.

- 2026-10-10: Texts were generic and repeated themselves; farms were just
  "a farm". He wants names and where things are, real facts, and fewer, more
  interesting places: junctions, villages and larger lakes over small farms.
  Examples of what he likes: fishing competitions at Selåsvatn and when they
  are, the height of the masts on Hovdefjell, beaver lodges by the lake at
  Selåsvatn, the history of a ruin.
