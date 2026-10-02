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

- **R-PROV-001** — The written manifest MUST contain exactly the fields
  `SPEC_GUIDELINES.md` §8 declares — no more, no less. That document is the
  single source of truth for the schema; this component's job is populating
  it, not redefining it.
- **R-PROV-002** — `spec_bundle_hash`, `model_pin`, `prompt_version`, and
  `sample_index` MUST be populated from `generator`'s `GenerationResult`.
- **R-PROV-003** — `gate_versions` MUST be populated by collecting each
  gate's own reported version (`cache-manager`, `criterion-compiler`,
  `license-scanner`, `secret-scanner`, `cross-model-divergence-checker`'s
  comparison logic, the mutation-testing harness) — never invented or
  hardcoded here.
- **R-PROV-004** — `cache_hit` MUST be populated from whichever gate
  reported it (primarily `generator`'s `GenerationResult.cache_hit`).
- **R-PROV-005** — `verification_report` MUST be populated from
  `verifier-orchestrator`'s `VerificationReport`, in full — not summarized
  or truncated, since this is the hard evidence trail for incident
  debugging (`SPEC_GUIDELINES.md` §8).
- **R-PROV-006** — `cross_model_check` MUST be populated with an explicit
  status, never a bare absence: `ran-no-divergence` / `ran-diverged` /
  `ran-second-failed` / `not-run` (toggle disabled or no second model
  configured). `not-run` is itself a value that must be written, never
  simply omitted — consistent with D10's "visible, not silent" posture for
  everything about model availability.
- **R-PROV-007** — `license_scan` and `secret_scan` MUST always be
  populated (both scans are unconditional, D7/D12 — there is no "not-run"
  state for either, unlike `cross_model_check`).
- **R-PROV-008** — `generated_at` MUST be this component's own write-time
  timestamp, not copied from any upstream component's internal timestamp.
- **R-PROV-009** — When `cache_hit` is `true` (D11), `verification_report`,
  `cross_model_check`, `license_scan`, and `secret_scan` MUST be copied
  verbatim from the matching prior commit's manifest (looked up via
  `cache-manager`'s own key), not recomputed — this is the concrete
  mechanism behind D11's "rollback is a cache-hit" claim, which nothing
  before this component actually implemented.
- **R-PROV-010** — The manifest MUST be written identically to both
  `gen/<component>/.provenance.json` and
  `verification/<component>/.provenance.json` — two copies of one logical
  artifact (per D7's original phrasing, "`gen/<component>/.provenance.json`
  (and `verification/<component>/`)"), which MUST NEVER be permitted to
  diverge.
- **R-PROV-011** — The written file MUST be syntactically valid JSON whose
  top-level keys exactly match `SPEC_GUIDELINES.md` §8's field set — no
  extra keys, no missing ones.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (the provenance manifest schema is `SPEC_GUIDELINES.md`
§8 itself — this component does not redefine it).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

None.

## Change log

- Initial draft.
