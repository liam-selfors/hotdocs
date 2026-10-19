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

**In scope:** frontmatter completeness and typing on a component's root file,
and frontmatter *absence* on every unit file (D15); cross-reference
resolution (`depends_on` / `realizes` / `uses_var` / `depends_on_guarantees`,
D16); dependency-graph acyclicity; `R-id`/`G-id` formation and RFC 2119
usage; forward and backward traceability between requirements and
acceptance criteria; acceptance-criterion well-formedness; glossary
conformance; the D2 size caps; `specs/vars/` secret-field safety; glossary
singularity (D14); no trailing whitespace anywhere in a spec file
(R-LINT-019) — keeps `spec_bundle_hash` (`spec-bundle-assembler`) safely
hashing raw bytes without a cosmetic-diff cache-hit cost.

**Out of scope:** generation; verification of generated code's actual
behavior. **Mostly, but not entirely, free of model calls and judgment** —
18 of 19 requirements are pure structural/textual checks; R-LINT-015 is a
deliberate, narrow exception (see its entry and `constraints.md`) for the one
case in this component's scope that is genuinely about meaning, not
structure, and D5 says exactly that's when `llm-judge` is the right tool.

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

Every criterion below is `kind: compiled` — nothing in this component's
behavior is runtime-behavior-of-generated-code or a judgment call; it is all
deterministic, rule-based logic over spec text, so none of it needs a second
model or an `llm-judge` evaluator. (A deliberate test of D5's own guidance:
"prefer `compiled` whenever the criterion is in principle about runtime
behavior... reach for `llm-judge` only for criteria no code test could
capture" — a linter is the cleanest possible case for that guidance to hold.)

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
- R-LINT-012's "interface surface elements" dimension: concretely defined in
  `SPEC_GUIDELINES.md` §4 and implemented in `gen/spec-linter/spec_linter.py`
  — one per distinct CLI invocation line in `interface/cli.md`, one per
  distinct function signature in `interface/library.md`, one per file under
  `interface/data/` (D15 — each already names exactly one type by
  construction, replacing the earlier "one per `## Data: ...` heading"
  counting once headings stopped being the unit boundary).

## Change log

- Initial draft.
