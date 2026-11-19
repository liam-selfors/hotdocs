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

Full narrative per entry lives in its own `specs/decisions/D<N>.md`.

- Initial draft.
- Renamed `component_doc_words`; added `R-CITE-001`/`027`.
- `D13`: rewired onto `graph-query-engine`'s shared views.
- `D70`–`D74`: added `R-CITE-003`–`030`.
- `D162`: added `R-LINT-031` (CLI coverage, warn only).
- `D77`: evaluated against `R-SIZE-002`'s crowding signal and
  deliberately not split.
- `D176`: `R-CITE-003`–`030` implemented, found never to have been;
  028 handles wrapped and punctuated citations.
- `D199`: `R-LINT-032`, a project component may not reuse a tool
  component's slug.
- `D208`: `load_corpus` and `Corpus` specified.
- `D242`: corpus loading, citation rules and size rules split out into
  `corpus-loader`, `citation-checker` and `size-checker`.
- `D343`: `R-LINT-034`, frontmatter `assets` and asset kind definitions.
- `D344`: `python` is never declared in `assets`.
