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

**In scope:** frontmatter completeness and typing on a component's root
file, and frontmatter *absence* on every unit file; cross-reference
resolution (`depends_on` / `realizes` / `uses_var` /
`depends_on_guarantees`); dependency-graph acyclicity; `R-id`/`G-id`
formation and RFC 2119 usage; forward and backward traceability
between requirements and acceptance criteria; acceptance-criterion
well-formedness; glossary conformance and citation resolution
(`R-LINT-028`); component size caps; `specs/vars/` secret-field
safety; glossary singularity; no trailing whitespace anywhere in a
spec file (`R-LINT-019`, keeps `spec_bundle_hash` hashing raw bytes
without a cosmetic-diff cache-hit cost).

**Out of scope:** generation; verification of generated code's actual
behavior. **Mostly free of model calls and judgment** — only
R-LINT-015 is a deliberate exception (see its entry and
`constraints.md`), genuinely about meaning, not structure.

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

None. See `verification/spec-linter/BOOTSTRAP.md` for resolved history.

## Change log

Full narrative per entry lives in its own `specs/decisions/D<N>.md`.

- Initial draft.
- `D40`–`D42`: renamed `component_doc_words`; added `R-LINT-026`/`027`.
- `D44`: rewired onto `graph-query-engine`'s shared views.
- `D86`: added `R-LINT-028`.
