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

**Out of scope:** generation; verification of generated code's actual
behavior. **Mostly, but not entirely, free of model calls and judgment** —
14 of 15 requirements are pure structural/textual checks; R-LINT-015 is a
deliberate, narrow exception (see its entry and `constraints.md`) for the one
case in this component's scope that is genuinely about meaning, not
structure, and D5 says exactly that's when `llm-judge` is the right tool.

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
- **R-LINT-011** — The linter MUST fail a `Definitions`-section entry for a
  glossary term whose local text is **near-verbatim identical** (normalized
  token-overlap ratio ≥ 0.8 against the glossary's own definition text) to
  `specs/glossary.md`'s definition — restating the definition is not a delta.
  This is a textual-similarity check only: deterministic, no model call, no
  judgment of meaning. (Resolved from an earlier, broader wording that didn't
  distinguish "restating" from "conflicting" — see R-LINT-015.)
- **R-LINT-012** — The linter MUST compute the six D2 size-cap dimensions per
  component and report each at `warn` or `fail` severity per the published
  thresholds.
- **R-LINT-013** — The linter MUST fail a `specs/vars/` declaration with
  `sensitivity: secret` that carries an `example` or `default` field.
- **R-LINT-014** — The linter MUST fail if more than one glossary-like file
  exists under `specs/` without a corresponding `architecture/`-level
  bounded-context split decision (D14).
- **R-LINT-015** — For a `Definitions`-section entry that names a glossary
  term but is *not* caught by R-LINT-011 (i.e. not a near-verbatim copy), the
  linter MUST run an `llm-judge` evaluation of whether the local text is
  consistent with (a permitted delta on) the glossary's definition, versus
  substantively conflicting with it (a true redefinition in different words).
  A conflict MUST be reported as a `fail`-severity finding with structured
  rationale (per `SPEC_GUIDELINES.md` §5). **When no model is configured at
  all, this one requirement MUST be skipped with a visible, non-silent
  notice** — not treated as passing, not a crash — the same "tool must keep
  working" posture D10 established for model-pin availability and
  `cache-manager` established for backing-store availability; this is now a
  third instance of that pattern, not a new one.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`LintReport` schema).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

_None. The three originally recorded here were resolved during the bootstrap
implementation (`verification/spec-linter/BOOTSTRAP.md` has the full
account); a fourth gap (interface-surface-element counting), flagged
separately after the bootstrap, is resolved below too. All four recorded here
as decisions, not left open:_

- RFC 2119 keyword list for R-LINT-007: the curated 5 (`MUST` / `MUST NOT` /
  `SHOULD` / `SHOULD NOT` / `MAY`) — directly answerable from
  `SPEC_GUIDELINES.md`'s own opening line, which already declares that as its
  keyword set.
- R-LINT-004's cycle detection: standard DFS tri-color (white/gray/black
  marking) — no genuine ambiguity once actually implemented.
- R-LINT-012's word/LOC counting is pre-compilation, and the question turned
  out to be moot: compiled test scaffolding doesn't exist at lint time at
  all (generation hasn't run yet), so there's nothing post-compilation to
  count regardless.
- R-LINT-012's "interface surface elements" dimension: now concretely
  defined in `SPEC_GUIDELINES.md` §4 and implemented in
  `gen/spec-linter/spec_linter.py` — one per distinct CLI invocation line,
  one per distinct `Library` function signature, one per `## Data: ...`
  heading. Previously flagged as having no canonical algorithm; resolved.

## Change log

- Initial draft.
