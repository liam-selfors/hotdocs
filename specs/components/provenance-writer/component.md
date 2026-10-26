---
id: comp-provenance-writer
title: Provenance Writer
status: draft
owners: [pipeline-team]
depends_on: [comp-generator, comp-verifier-orchestrator, comp-license-scanner, comp-secret-scanner, comp-cache-manager]
realizes: [P-ZERO-EDIT, P-COMPLIANCE-GATE]
sealed: false
---

# Provenance Writer

## Purpose

Assembles `.provenance.json` (`SPEC_GUIDELINES.md` §7) from every other
gate component's own output, and writes it. The single place that schema is
populated — every other component reports its own result; this component
collects, never invents.

## Scope

**In scope:** collecting each dependency's reported output into the one
canonical schema; writing it to both required locations; the
provenance-hit copy-forward behavior (D11).

**Out of scope:** deciding *whether* a component's result is a
provenance hit (`provenance-checker`/`merge-orchestrator` already
decided that and supplied the already-sourced fields by the time this
component runs, `D39`); running any gate itself.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`. (the provenance manifest schema is `SPEC_GUIDELINES.md`
§7 itself — this component does not redefine it).

## Acceptance criteria

See `acceptance/`.

All ten criteria are `kind: compiled` — collecting and writing already-
produced results is pure, deterministic logic. A sixth component in this
corpus with a fully `compiled` acceptance set.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
- `D39`: `cache_hit` renamed `provenance_hit` throughout (`R-PROV-004`);
  `R-PROV-009`'s lookup is now the caller's job, not this component's —
  `cache-manager` never held a `VerificationReport` to look up.
