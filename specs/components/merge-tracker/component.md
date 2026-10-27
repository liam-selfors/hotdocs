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

**Since D19, also writes `AttemptRecord`s to `.hotdocs/attempts/`** — the
full `GenerationResult`/`VerificationReport` for one component's one
generation attempt per merge, taken as direct parameters the same way
merge-level facts already are. A separate store from `TrackingRecord`,
not a change to its deliberately flattened shape — this closes the gap
`D3`'s retirement of best-of-k opened: a blocked merge commits no
provenance at all, so without this, a failed attempt's full diagnostic
detail would exist only in `merge-orchestrator`'s process memory for one
merge, then vanish.

**Since D3, also exposes `last_requirement_failures`** — a pure,
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

- ~~Whether `merge-orchestrator` calling this component should be a hard
  requirement... or whether a failure to write a tracking record should
  itself be surfaced somewhere visible...~~ — resolved (`D25`):
  best-effort, never silent, confirmed as both at once rather than a
  choice between them. The non-gating half was already settled by
  `R-MERGE-019`/`R-MERGE-021` and this component's own `R-TRACK-005` —
  a write failure here MUST NOT alter the merge's outcome. The
  visibility half: `merge-orchestrator` now catches a failed call and
  surfaces it as `MergeResult.tracking_write_error` — `{category,
  message}`, the same structured shape `llm-endpoint`'s
  `model_call_error` already established (`D20`) for exactly this kind
  of "degrade silently in function, never in visibility" requirement.
  Chosen over inventing a new channel (a stderr line, a sentinel file
  under `.hotdocs/`) because `MergeResult` is already the one place
  every merge attempt's outcome is reported, in both `--format=json`
  and `--format=text` — a second, parallel reporting path for one
  specific failure mode would be exactly the kind of unrequested
  abstraction this corpus avoids (D4/D6). See `R-MERGE-019` and
  `AC-MERGE-024` for the normative behavior; this component's own
  `R-TRACK-005` is unchanged.

## Change log

- Initial draft.
- `D25`: closed the best-effort/visibility open question —
  `merge-orchestrator`'s `R-MERGE-019` now owns the catch-and-surface
  behavior; nothing changes here.
- `D29`: `TrackingRecord.components[].cache_hit` renamed
  `provenance_hit` (`R-TRACK-002`).
