---
id: comp-merge-tracker
title: Merge Tracker
status: draft
owners: [pipeline-team]
depends_on: [comp-provenance-writer]
realizes: [P-MERGE-VISIBILITY]
sealed: false
---

# Merge Tracker

## Purpose

Writes a durable, local-only record of every merge attempt —
success or block — so a developer can see per-component status after the
fact without having kept the CLI output, and so re-running a blocked merge
(`R-MERGE-018`) is visibly, not just theoretically, free for the
components that already succeeded. Not a gate: nothing about pass/fail
depends on this component or anything it writes (`SPEC_GUIDELINES.md`
§1's `.hotdocs/` boundary) — it observes merges, it does not influence
them.

## Scope

**In scope:** assembling one tracking record per merge attempt from
merge-level facts (`changed_ids`, `block_reasons`, overall outcome) handed
to it directly, plus per-component detail read from `provenance-writer`'s
already-written manifests (present in the working tree by the time this
component runs, whether or not the merge ultimately commits — the same
"read what's already on disk" pattern `review-packet-builder` already
uses, chosen specifically so this component does not need to depend on
`merge-orchestrator`'s own `MergeResult` type, which would create a
dependency cycle); writing that record to `.hotdocs/tracking/` as one JSON file per
attempt, in a shape DuckDB's core `read_json` function (no extension
needed — unlike `specs/architecture/graph-query-engine.md`'s frontmatter
use case, this is schema-controlled data this component itself defines,
not someone else's existing file format) can glob directly.

**Out of scope:** deciding merge outcomes (that's `merge-orchestrator`'s
and every gate's job — this component runs strictly after); providing a
bespoke query API. Querying is DuckDB pointed at `.hotdocs/tracking/*.json`
directly — this component's job ends at writing a well-documented,
directly-queryable shape, not building a second query layer on top of a
database that already is one.

**Since D32, also writes `AttemptRecord`s to `.hotdocs/attempts/`** — the
full `GenerationResult`/`VerificationReport` for one component's one
generation attempt per merge, taken as direct parameters the same way
merge-level facts already are. A separate store from `TrackingRecord`,
not a change to its deliberately flattened shape — this closes the gap
`D31`'s retirement of best-of-k opened: a blocked merge commits no
provenance at all, so without this, a failed attempt's full diagnostic
detail would exist only in `merge-orchestrator`'s process memory for one
merge, then vanish.

**Since D33, also exposes `last_requirement_failures`** — a pure,
read-only convenience over `.hotdocs/attempts/` that tells a developer
which `R-id`s a component's last attempt failed, so they can decide
whether to pass them as `retry_feedback` on their next `hotdocs merge`
call (`R-MERGE-022`). Never called by the merge pipeline itself — this
component answers "what failed," it never decides "retry with this."

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

All eight criteria are `kind: compiled` — assembling already-produced facts
into a JSON file is pure, deterministic logic; nothing here needs a model
or judgment, same case `spec-bundle-assembler`/`provenance-writer` already
made.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Whether `merge-orchestrator` calling this component should be a hard
  requirement (a merge attempt that somehow fails to write a tracking
  record is still a successful or blocked merge either way — this
  component is explicitly non-gating) or whether a failure to write a
  tracking record should itself be surfaced somewhere visible (silently
  losing observability data is still a silent failure, just not a
  merge-blocking one). Not resolved here; leaning toward "best-effort,
  but never silent about the attempt itself" without having picked the
  exact visibility mechanism.

## Change log

- Initial draft.
