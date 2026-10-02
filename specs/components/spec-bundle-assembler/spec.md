---
id: comp-spec-bundle-assembler
title: Spec Bundle Assembler
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter]
realizes: [P-ZERO-EDIT]
model_pin: claude-sonnet-5
sealed: false
---

# Spec Bundle Assembler

## Purpose

Assembles a component's full generation input — its own `spec.md` +
`interface.md` + `constraints.md`, its dependencies' `interface.md`s, its
referenced `specs/vars/` declarations, and `specs/glossary.md` — into one
payload (`SpecBundle`). Reused by canonical generation, the cross-model
divergence check, and hint-mode previews — one assembly implementation, not
three.

## Scope

**In scope:** reading and concatenating the right files for a given
component id; computing `spec_bundle_hash`; the cold-vs-hint distinction
(D1) at the bundle level.

**Out of scope:** calling any model (`generator`'s job); deciding *whether*
to regenerate (`impact-analyzer`'s job); verifying anything.

## Definitions

No deltas from `specs/glossary.md`.

## Behavior

- **R-ASSEMBLE-001** — The bundle MUST include the target component's own
  `spec.md`, `interface.md`, and `constraints.md`. It MUST NOT include
  `acceptance.md`. This is deliberate, not an oversight: the generation
  model seeing its own acceptance criteria risks overfitting to specific
  test assertions rather than genuinely implementing the normative Behavior
  section — already implied by `SPEC_GUIDELINES.md` §6 step 2's bundle
  definition, made an explicit, enforced requirement here for the first
  time.
- **R-ASSEMBLE-002** — For each id in the component's `depends_on`, the
  bundle MUST include that component's `interface.md` only — never its
  `spec.md` or `constraints.md`. A dependent needs the contract, not the
  internal rationale; this is the same interface-vs-internal distinction
  `impact-analyzer` already established for blast-radius propagation
  (R-IMPACT-002/003), applied here to what a dependent is allowed to *see*,
  not just what triggers its regeneration.
- **R-ASSEMBLE-003** — For each id in the component's `uses_var`, the bundle
  MUST include that `specs/vars/` declaration's full content (name, type,
  required/optional, description, sensitivity — never a value, because
  there is none to include).
- **R-ASSEMBLE-004** — The bundle MUST include the full current content of
  `specs/glossary.md`.
- **R-ASSEMBLE-005** — Assembly MUST fail (refuse to produce a bundle,
  returning a precondition-failure result, not a partial one) if the corpus
  does not pass `spec-linter` cleanly at hard-fail severity. Mirrors
  `impact-analyzer`'s R-IMPACT-007.
- **R-ASSEMBLE-006** — The assembled bundle MUST be a deterministic function
  of corpus content — the same spec/interface/constraints/vars/glossary
  bytes always produce the same bundle bytes. Required for `spec_bundle_hash`
  to mean anything as a cache key (D11/D13).
- **R-ASSEMBLE-007** — The assembler MUST compute and expose
  `spec_bundle_hash` — a content hash of the full assembled bundle — as part
  of its output.
- **R-ASSEMBLE-008** — In `hint` mode (vs. the default `cold` mode), the
  bundle MUST additionally include the component's *current*
  `gen/<component>/` content as a clearly separate `hint_code` field — never
  merged into, or indistinguishable from, the cold bundle's own fields. This
  is D1's hint-vs-cold distinction, concretely implemented at the bundle
  level for the first time; nothing before this assigned which component
  actually produces the two different payloads D1 describes.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`SpecBundle` schema).

## Acceptance criteria

See `acceptance.md`.

## Non-functional constraints

See `constraints.md`.

## Open questions

- Whether `spec_bundle_hash` should hash the files' raw bytes or a
  normalized form (e.g. with trailing whitespace stripped) — raw bytes is
  the safer default (never hides a real content difference) but means an
  inconsequential whitespace-only edit still forces a full cache miss. Not
  resolved here; a candidate refinement once real cache-hit-rate data
  exists.

## Change log

- Initial draft.
