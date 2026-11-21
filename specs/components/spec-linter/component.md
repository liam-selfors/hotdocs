---
id: comp-spec-linter
title: Spec Linter
status: draft
owners: [pipeline-team]
depends_on: [comp-graph-query-engine, comp-corpus-loader, comp-citation-checker, comp-size-checker]
realizes: [P-AMBIGUITY-GATE]
model_pin: claude-opus-5-5
sealed: false
---

# Spec Linter

## Purpose

Mechanically validates a spec corpus against `SPEC_GUIDELINES.md`'s
structural, traceability, citation and size-cap rules, before anything
downstream (impact analysis, generation, verification) runs. It is the pipeline's first
gate and the component everything else assumes has already run.

## Scope

**In scope:** every rule in `requirements/`, one report and CLI that also
carry the findings of `citation-checker` and `size-checker`, and
re-exporting `corpus-loader`'s `load_corpus`.

**Out of scope:** generation; verifying generated code's actual
behavior. **Mostly free of model calls and judgment** — only
R-LINT-015 is a deliberate exception, about meaning.

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

All `generated-test`, except the two `llm-judge` criteria for
R-LINT-015's meaning check.

## Non-functional constraints

See `constraints.md`.

## Open questions

None. See `verification/spec-linter/BOOTSTRAP.md` for resolved history.

## Change log

See `D13`, `D70`–`D74`, `D77`, `D162`, `D176`, `D199`, `D208`, `D242`,
`D343`, `D344` and `D354`.
