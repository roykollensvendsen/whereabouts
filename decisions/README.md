# Decision records

A decision that costs more to reverse than to take is written down here before
the code that rests on it. A decision that only implements one already taken
is not; it is a commit message.

## The form

Every record is `ADR-W-NNN-a-short-title.md`, with these sections in
this order:

| Section | Holds |
|---|---|
| Status | Accepted or Proposed, who decided, when; an objection returns it to Proposed |
| Context | what was true when the question arose, with sources where the facts are checkable |
| Options considered | every option weighed, including doing nothing, each with why it was not taken |
| Decision | what was chosen, in one paragraph |
| Consequences | what this costs, what it forecloses, and at least one thing that gets worse |
| Related | the pages it shapes |

Numbers are one sequence and never reused. A record is superseded by a later
one, never edited into a different decision.

Record the process choices too, not only the artefact ones. How a change is
made, and why, is what costs time on every future contribution, and it is the
decision nobody writes down.

## The records

| Id | Decides | Status |
|---|---|---|
| [W-001](ADR-W-001-a-service-of-its-own-on-this-machine-answering-over-mcp.md) | A service of its own, on this machine, answering over MCP | Accepted |
| [W-002](ADR-W-002-the-route-is-kept-thirty-days-on-this-machine.md) | The route is kept thirty days on this machine, and wiped on request | Accepted |
| [W-003](ADR-W-003-a-change-is-a-pull-request-made-in-step-with-the-bridge.md) | A change is a pull request, made in step with the voice bridge | Accepted |
| [W-004](ADR-W-004-places-are-described-here-and-told-by-the-phone.md) | Places are described here, kept, and told by the phone as Roy passes | Accepted |

What is deliberately left undone, and what would make each worth doing, is
[`deferred.md`](deferred.md). A thing left undone with no trigger is a thing
forgotten.
