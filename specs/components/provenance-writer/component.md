---
id: comp-provenance-writer
title: Provenance Writer
status: draft
owners: [pipeline-team]
depends_on: [comp-generator, comp-verifier-orchestrator, comp-cross-model-divergence-checker, comp-license-scanner, comp-secret-scanner, comp-cache-manager]
realizes: [P-ZERO-EDIT, P-COMPLIANCE-GATE]
sealed: false
---

# Provenance Writer

## Purpose

Assembles `.provenance.json` (`SPEC_GUIDELINES.md` §8) from every other
gate component's own output, and writes it. The single place that schema is
populated — every other component reports its own result; this component
collects, never invents.

## Scope

**In scope:** collecting each dependency's reported output into the one
canonical schema; writing it to both required locations; the cache-hit
copy-forward behavior (D11).

**Out of scope:** deciding *whether* a merge is a cache hit (`cache-manager`
already decided that by the time this component runs); running any gate
itself.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`. (the provenance manifest schema is `SPEC_GUIDELINES.md`
§8 itself — this component does not redefine it).

## Acceptance criteria

See `acceptance/`.

All eleven criteria are `kind: compiled` — collecting and writing already-
produced results is pure, deterministic logic. A seventh component in this
corpus with a fully `compiled` acceptance set.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
