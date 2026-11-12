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

All ten criteria are `kind: compiled` — collecting and writing already-
produced results is pure, deterministic logic. A sixth component in this
corpus with a fully `compiled` acceptance set.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
- `D29`: `cache_hit` renamed `provenance_hit` throughout (`R-PROV-004`);
  `R-PROV-009`'s lookup is now the caller's job, not this component's —
  `cache-manager` never held a `VerificationReport` to look up.
- `D67`: found via a pre-generation audit, before this component was
  ever built: `pipeline_version` and `verification_run_id` had no
  stated source anywhere. `R-PROV-012`/`013` fix this — the former is
  this component's own version constant, the latter a deterministic
  `"<slug>-attempt-<attempts>"`. Also found `R-PROV-002`'s claim that
  `spec_bundle_hash` comes from `generator`'s `GenerationResult` was
  false against that component's real schema at the time — fixed
  there instead (`GenerationResult` gained the field, `R-GEN-017`),
  since `provenance-writer` has no other dependency that could supply it.
- `D128`: real cold-generation, first attempt. `inputs` itself (not
  only fields nested inside it) MUST be read via dual
  dict-or-attribute access, never bare `.attr` (`R-PROV-014`,
  `AC-PROV-014`) — the identical bug class `R-TRACK-012` closed for
  `provenance-tracker`, one level removed: there, a called
  dependency's return value; here, a parameter the caller hands in
  directly.
- `D130`: `main()`'s CLI entry point (`interface/cli.md`) had no
  requirement or acceptance criterion at all, leaving its
  argument-parsing and exit-code branches permanently unexercised —
  caught by mutation score, not a failing assertion (`R-PROV-015`,
  `AC-PROV-015`).
- `D131`: converting a nested upstream value for writing MUST handle
  any attribute-bearing object (e.g. `SimpleNamespace`), not only a
  dict or a `dataclasses` instance (`R-PROV-016`) — the same `D94`
  shape range `R-PROV-014` already required on the read side.
- `D132`: `ProvenanceInputs` MUST remain a real, importable
  `dataclass` in this module, never dropped in favor of duck-typed
  `Any` alone (`R-PROV-017`) — matching every sibling component's own
  `interface/data/` type (`cache-manager`'s `CachedResult`,
  `license-scanner`'s `LicenseScanResult`). Full account in
  `BOOTSTRAP.md`.
- `D170`: `write_sealed_provenance` and the `SealedProvenance` schema
  (`R-PROV-018`/`019`): a sealed component's own provenance file.
  Regenerated and landed at 20/20, `mutation_score` 0.87.
