---
id: comp-spec-linter
title: Spec Linter
status: draft
owners: [pipeline-team]
depends_on: [comp-graph-query-engine]
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
behavior. **Mostly free of model calls and judgment** — 18 of 19
requirements are pure structural/textual checks; R-LINT-015 is a
deliberate, narrow exception (see its entry and `constraints.md`) for the
one case here that's genuinely about meaning, not structure, and D5 says
that's when `llm-judge` is the right tool.

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

Every criterion below is `kind: compiled` except R-LINT-015's
(`llm-judge`) — deterministic, rule-based logic over spec text needs
neither a second model nor a judgment call.

## Non-functional constraints

See `constraints.md`.

## Open questions

_None — all four originally recorded here were resolved during the
bootstrap implementation; `verification/spec-linter/BOOTSTRAP.md` has
the full account (RFC 2119 keyword list, cycle-detection algorithm,
word/LOC counting scope, interface-surface-element counting)._

## Change log

- Initial draft.
- `D40`–`D42`: `spec_bundle_words` renamed `component_doc_words`;
  added `R-LINT-026`/`027`; `component_doc_words` now queries the
  shared `component_size` view (first real `duckdb` dependency).
- `D44`: `R-LINT-003`/`004`/`008`/`009`/`018` rewired onto
  `graph-query-engine`'s shared `nodes`/`edges` views; `depends_on`
  now `[comp-graph-query-engine]`.
