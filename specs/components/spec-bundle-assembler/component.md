---
id: comp-spec-bundle-assembler
title: Spec Bundle Assembler
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter]
realizes: [P-ZERO-EDIT]
model_pin: claude-sonnet-5
sealed: false
---

# Spec Bundle Assembler

## Purpose

Assembles a component's full generation input — its own `component.md` +
`requirements/` + `interface/` + `constraints.md`, its dependencies'
`interface/` content, its referenced `specs/vars/` declarations, and
`specs/glossary.md` — into one payload (`SpecBundle`). Reused by canonical
generation and hint-mode previews — one assembly implementation, not two.

## Scope

**In scope:** reading and concatenating the right files for a given
component id; computing `spec_bundle_hash`; the cold-vs-hint distinction
(D1) at the bundle level.

**Out of scope:** calling any model (`generator`'s job); deciding *whether*
to regenerate (`impact-analyzer`'s job); verifying anything.

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

Every criterion is `kind: compiled` — reading, concatenating, and hashing
files is pure, deterministic logic; nothing here needs a model or judgment.
The third component in this corpus for which that's true of 100% of its
acceptance criteria.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Whether `spec_bundle_hash` should hash the files' raw bytes or a
  normalized form (e.g. with trailing whitespace stripped) — raw bytes is
  the safer default (never hides a real content difference) but means an
  inconsequential whitespace-only edit still forces a full cache miss. Not
  resolved here; a candidate refinement once real cache-hit-rate data
  exists.

## Change log

- Initial draft.
