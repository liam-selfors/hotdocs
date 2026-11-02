---
id: comp-spec-bundle-assembler
title: Spec Bundle Assembler
status: draft
owners: [pipeline-team]
depends_on: [comp-graph-query-engine, comp-spec-linter]
realizes: [P-ZERO-EDIT]
model_pin: claude-opus-5-5
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

The cold-vs-hint split traces to the original brainstorm.

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
- First real `gen/spec-bundle-assembler/` implementation — a
  hand-authored bootstrap exception, temporary like `cache-manager`.
  `depends_on` gained `comp-graph-query-engine` (R-ASSEMBLE-010 already
  required reading dependency `Purpose` text via its `component_context`
  view; the dependency was never declared).
- `D37`: `R-ASSEMBLE-011` — `dependency_usage`, a new, third
  `dependency_*` field, mechanically introspected from a dependency's
  real `gen/` code (never its spec), the one-directional fix for
  `D46`'s import-path failure.
- `D60`: `_dependency_usage` now checks a sealed dependency's declared
  `source_path` before falling back to `gen/<dependency>/` — every
  sealed dependency's usage card had been silently degrading to empty,
  indistinguishable from "no real code yet," found only once a real
  dependent needed real usage info for `criterion-compiler` for the
  first time.
- `D69`: `R-ASSEMBLE-001` now excludes the target's own `## Rationale`/
  `## Open questions`/`## Change log` — the same "contract, not
  rationale" principle `R-ASSEMBLE-002` already applied to every
  dependency, found (via a prompt-efficiency audit) never applied to
  the target itself. Measured at 15-60% of a real component.md's body.
- `D100`: `R-ASSEMBLE-009`'s `CriterionBundle` gains
  `dependency_interfaces`, the same content and the same
  `R-ASSEMBLE-002` rule `SpecBundle.dependency_interfaces` already
  follows — found only once a real `generated-test` authoring for a
  component with real dependencies had no authoritative source for a
  dependency's real call signature or return shape and guessed wrong,
  despite that shape already being fully documented and already
  available to `generator` via this exact mechanism. New
  `AC-ASSEMBLE-013`. Purely additive — `assemble()`/`SpecBundle`
  unchanged.
- `D101`: `R-ASSEMBLE-012` — both functions MUST read corpus structure
  exclusively through `spec-linter`'s own parsed `Corpus`/`Component`
  objects, never by independently re-parsing frontmatter, and MUST NOT
  introduce a new third-party dependency for anything a declared
  dependency already provides. Found only once a real cold-generation
  candidate reinvented frontmatter parsing with `PyYAML`, a package
  this corpus has never installed. New `AC-ASSEMBLE-014`.
- `D109`: cold-generated for the first time, closing the
  `cache-manager`/`spec-bundle-assembler` "temporary exception" noted
  above — `model_pin` moves to `claude-opus-5-5`. 11/14 criteria pass;
  full arc and the three remaining known limitations documented in
  `BOOTSTRAP.md`. The old hand-written `test_spec_bundle_assembler.py`
  suite is retired, fully superseded by per-criterion `generated-test`
  files (confirmed incompatible with the new candidate's own naming
  — `PreconditionFailureError` renamed `PreconditionFailure` — and its
  one test without a direct `AC-id` match, the sealed-dependency
  `source_path` case, is covered inside the new `AC-ASSEMBLE-011`
  fixture too).
- `D114`: `R-ASSEMBLE-013` — `dependency_interfaces` now also
  resolves, one level deep, any type a dependency's own interface
  text names but doesn't itself own, searching the whole corpus for
  its real owner (skipped on no match or more than one) — the
  transitive-type gap deferred twice (`D110`, `D112`) until
  `provenance-tracker`'s own bootstrap actually hit it. New
  `AC-ASSEMBLE-015`.
- `D118`: second cold-generation round lands at 14/15 (up from
  `D109`'s 11/14); `D116`/`D117` closed two knock-on test-author gaps
  along the way (a stale `spec-linter` interface doc, a self-check
  needing a literal worked call). The one remaining failure,
  `AC-ASSEMBLE-011`, traces to `graph-query-engine`'s own pre-existing
  decision-nodes gap (confirmed via its own suite, predates this
  session) — a known limitation, not chased here. `AC-ASSEMBLE-007`'s
  prior known limitation no longer reproduces. (`D177` corrected that
  cause: the generated test's fixture had no frontmatter.)
- `D177`: `AC-ASSEMBLE-011` states its fixture corpus must pass
  `spec-linter`. Its generated test still fails (a `test-author`
  weakness, recorded in `D177`); code and landed tests unchanged.
