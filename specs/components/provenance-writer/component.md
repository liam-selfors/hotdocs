---
id: comp-provenance-writer
title: Provenance Writer
status: draft
owners: [pipeline-team]
depends_on: [comp-generator, comp-verifier-orchestrator, comp-license-scanner, comp-secret-scanner, comp-cache-manager]
realizes: [P-ZERO-EDIT, P-COMPLIANCE-GATE]
model_pin: claude-opus-5-5
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
provenance-hit copy-forward behavior. Also the sealed
counterpart: writing a sealed component's ownership and verification
manifest (`R-PROV-018`/`019`), whose schema this component owns.

**Out of scope:** deciding *whether* a component's result is a
provenance hit (`provenance-checker`/`component-gate-runner` already
decided that and supplied the already-sourced fields by the time this
component runs, `D29`/`D76`); running any gate itself.

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

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

Initial draft, then `D29`, `D67`, `D128`, `D130`, `D131`, `D132` and
`D170`: see the decisions. `D343`: the manifest records each asset's
kind, definition, adapter and environment (`R-PROV-022`).
