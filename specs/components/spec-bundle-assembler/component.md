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

## Non-functional constraints

See `constraints.md`.

## Open questions

- ~~Whether `spec_bundle_hash` should hash the files' raw bytes or a
  normalized form (e.g. with trailing whitespace stripped)~~ — resolved:
  raw bytes, permanently, not provisionally. Normalizing the hash itself
  was rejected once a concrete risk surfaced: these are Markdown files, and
  Markdown is not whitespace-insensitive (two-or-more trailing spaces are
  CommonMark's hard-line-break syntax; indentation is load-bearing inside
  nested lists and code fences) — there is no universally-safe
  normalization rule to hash against instead, so "ignore whitespace
  differences" risks silently treating two *meaningfully* different
  bundles as identical. The cache-hit-rate concern this question raised is
  real but belongs at a different layer: `spec-linter`'s new R-LINT-019
  rejects trailing whitespace outright, so the cosmetic diff never reaches
  a committed file in the first place — the hash stays simple and
  trustworthy, and the cache-hit benefit is real rather than approximate.

## Change log

- Initial draft.
