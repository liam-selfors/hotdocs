---
id: comp-impact-analyzer
title: Impact Analyzer
status: draft
owners: [pipeline-team]
depends_on: [comp-spec-linter]
realizes: [P-ZERO-EDIT]
model_pin: claude-sonnet-5
sealed: false
---

# Impact Analyzer

## Purpose

From a set of changed spec ids, computes the minimal **blast radius** (the
term as defined in `specs/glossary.md`) — the set of components that actually
need regeneration or re-verification for this change. Runs after
`spec-linter` passes, assuming a validated, acyclic, reference-resolved
corpus graph; it does not re-validate that graph itself.

## Scope

**In scope:** determining, for a given set of changed spec ids, which
components are directly changed and which are transitively impacted because
something they depend on changed in a way that affects their contract.
Distinguishing a dependency's *contract* changing from its *internals*
changing, so an unrelated component's change doesn't force regeneration of
everything downstream of it.

**Out of scope:** generation itself; deciding *how* to regenerate a component,
only *whether* it's in scope this merge; re-running `spec-linter`'s own
checks.

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

Every criterion below is `kind: compiled` — blast-radius computation is a
pure graph traversal over corpus state, the same demonstration `spec-linter`
already made for D5's "prefer `compiled` whenever possible" guidance, applied
to a second real component.

## Non-functional constraints

See `constraints.md`.

## Open questions

- R-IMPACT-002/003 define contract-change detection as "is `interface.md`
  byte-identical." This is simple and correct but blunt — a purely
  cosmetic `interface.md` edit (fixing a typo in a worked example, with no
  change to any declared type/endpoint) would still trigger full transitive
  regeneration under this rule. A semantic diff (did the actual declared
  contract change, not just the file's bytes) would be more precise but adds
  real complexity (parsing `interface.md`'s structure, not just hashing it).
  Left as byte-identical for this draft; semantic diffing is a candidate
  refinement, not a correctness requirement — a false-positive (unnecessary
  regen) is safe, just wasteful, unlike a false-negative.
- Should `R-IMPACT-004`/`005`'s transitive inclusion itself cascade further
  (e.g., does a component pulled in via `transitive-var` propagate to *its*
  dependents if its own `interface.md` is thereby considered changed)? As
  written, no — `uses_var`/`realizes` inclusion is one hop, not transitively
  re-applied. Not yet stress-tested against a real multi-hop corpus.

## Change log

- Initial draft.
