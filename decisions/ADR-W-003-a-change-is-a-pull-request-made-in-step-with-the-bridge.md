# ADR-W-003: A change is a pull request, made in step with the voice bridge

## Status

Accepted, by Roy Kollen Svendsen, 2026-10-10, as the way voice-integration and
claude-voice already work.

## Context

whereabouts is fed by the voice bridge and asked by Hermes. A change to what a
reading holds, or to a tool's answer, breaks one of them unless both sides
change together.

## Options considered

**Push to `main` directly.** Not taken. A change would reach a running service
without its checks having run.

**A pull request, merged by rebase once the checks are green.** Taken.

## Decision

Every change is a pull request, merged by rebase when its checks are green. A
change to the reading's shape or to a tool's answer is made on both sides, in
whereabouts and in voice-integration, and tried together before either is
merged. Commit messages follow the commit skill: everyday words first, and the
mechanics in a section at the bottom.

## Consequences

Nothing reaches the running service unchecked, and the two sides never
disagree for long. The cost is a slower change, and two pull requests for one
idea.

## Related

[`CONTRIBUTING.md`](../CONTRIBUTING.md).
