---
id: comp-spec-linter
title: Spec Linter
status: draft
owners: [pipeline-team]
depends_on: []
realizes: [P-AMBIGUITY-GATE]
model_pin: claude-sonnet-5
sealed: false
---

# Spec Linter

## Purpose

Mechanically validates a spec bundle against `SPEC_GUIDELINES.md`'s
structural, traceability, and size-cap rules, before anything downstream
(impact analysis, generation, verification) runs. It is the pipeline's first
gate and the component everything else assumes has already run.

## Scope

**In scope:** frontmatter completeness and typing; cross-reference resolution
(`depends_on` / `realizes` / `uses_var`); dependency-graph acyclicity; `R-id`
formation and RFC 2119 usage; forward and backward traceability between
requirements and acceptance criteria; acceptance-criterion well-formedness;
glossary conformance; the D2 size caps; `specs/vars/` secret-field safety;
glossary singularity (D14).

**Out of scope:** anything requiring a model call or judgment (ambiguity of
*meaning*, not structure — that's `llm-judge`'s job elsewhere); generation;
verification of generated code's actual behavior.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

- **R-LINT-001** — The linter MUST verify that every spec file's frontmatter
  contains all fields `SPEC_GUIDELINES.md` §2 marks required for that
  document's type, correctly typed (e.g. `depends_on` is a list, `sealed` is a
  boolean).
- **R-LINT-002** — The linter MUST fail any spec with `status: ratified` that
  has a non-empty "Open questions" section, or lacks a `last_ratified_commit`.
- **R-LINT-003** — The linter MUST resolve every `depends_on`, `realizes`, and
  `uses_var` entry against the corpus and fail on any entry that does not
  resolve to an existing, non-`deprecated` spec id.
- **R-LINT-004** — The linter MUST verify the corpus-wide `depends_on` graph
  contains no cycles.
- **R-LINT-005** — The linter MUST fail a component with `sealed: true` and no
  `source_path`, and MUST fail a component with `source_path` set but
  `sealed` false or absent.
- **R-LINT-006** — The linter MUST fail a non-`sealed` component with zero
  `realizes` entries.
- **R-LINT-007** — The linter MUST verify every requirement in a `spec.md`
  Behavior section has a unique `R-<comp>-NNN` id and uses at least one RFC
  2119 keyword.
- **R-LINT-008** — The linter MUST fail any `R-id` with zero covering
  acceptance criteria (forward traceability).
- **R-LINT-009** — The linter MUST fail any `Covers:` tag that does not
  resolve to a real `R-id` or `P-id` in the corpus (backward traceability).
- **R-LINT-010** — The linter MUST fail any acceptance criterion missing a
  `kind` or a complete Given/When/Then block.
- **R-LINT-011** — The linter MUST fail a spec whose `Definitions` section
  redefines a term already defined in `specs/glossary.md`, rather than only
  adding a delta.
- **R-LINT-012** — The linter MUST compute the six D2 size-cap dimensions per
  component and report each at `warn` or `fail` severity per the published
  thresholds.
- **R-LINT-013** — The linter MUST fail a `specs/vars/` declaration with
  `sensitivity: secret` that carries an `example` or `default` field.
- **R-LINT-014** — The linter MUST fail if more than one glossary-like file
  exists under `specs/` without a corresponding `architecture/`-level
  bounded-context split decision (D14).

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`LintReport` schema).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Exact RFC 2119 keyword list to accept for R-LINT-007 — the full RFC 2119 set
  (MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT,
  RECOMMENDED, MAY, OPTIONAL), or a curated subset matching this project's
  actual usage (MUST / MUST NOT / SHOULD / SHOULD NOT / MAY, as used
  throughout `SPEC_GUIDELINES.md`)?
- Canonical algorithm/library for R-LINT-004's cycle detection — any correct
  topological-sort-based approach is acceptable; no preference recorded yet.
- Does R-LINT-012's size-cap computation count words/LOC before or after
  Gherkin-block compilation? (Affects whether `acceptance.md`'s compiled test
  scaffolding counts toward the component's own cap.)

## Change log

- Initial draft.
