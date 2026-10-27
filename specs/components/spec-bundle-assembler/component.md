---
id: comp-spec-bundle-assembler
title: Spec Bundle Assembler
status: draft
owners: [pipeline-team]
depends_on: [comp-graph-query-engine, comp-spec-linter]
realizes: [P-ZERO-EDIT]
model_pin: claude-sonnet-5
sealed: false
---

# Spec Bundle Assembler

## Purpose

Assembles a component's full generation input — its own `component.md` +
`requirements/` + `interface/` + `constraints.md`, its dependencies'
`interface/` content and `Purpose` text, its referenced `specs/vars/`
declarations, and `specs/glossary.md` — into one payload (`SpecBundle`).
Reused by canonical generation and hint-mode previews — one assembly
implementation, not two.

## Scope

**In scope:** reading and concatenating the right files for a given
component id; computing `spec_bundle_hash`; the cold-vs-hint distinction
at the bundle level; including each dependency's `Purpose` text
alongside its `interface/` content (`R-ASSEMBLE-010`), so a generating
model sees not just a dependency's contract but what it's for.

## Rationale

The cold-vs-hint split traces to D1.

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
- `D49`: first real `gen/spec-bundle-assembler/` implementation — a
  hand-authored bootstrap exception, temporary like `cache-manager`.
  `depends_on` gained `comp-graph-query-engine` (R-ASSEMBLE-010 already
  required reading dependency `Purpose` text via its `component_context`
  view; the dependency was never declared).
- `D55`: `R-ASSEMBLE-011` — `dependency_usage`, a new, third
  `dependency_*` field, mechanically introspected from a dependency's
  real `gen/` code (never its spec), the one-directional fix for
  `D54`'s import-path failure.
- `D76`: `_dependency_usage` now checks a sealed dependency's declared
  `source_path` before falling back to `gen/<dependency>/` — every
  sealed dependency's usage card had been silently degrading to empty,
  indistinguishable from "no real code yet," found only once a real
  dependent needed real usage info for `criterion-compiler` for the
  first time.
- `D85`: `R-ASSEMBLE-001` now excludes the target's own `## Rationale`/
  `## Open questions`/`## Change log` — the same "contract, not
  rationale" principle `R-ASSEMBLE-002` already applied to every
  dependency, found (via a prompt-efficiency audit) never applied to
  the target itself. Measured at 15-60% of a real component.md's body.
