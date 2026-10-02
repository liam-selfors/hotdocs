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

- **R-IMPACT-001** — The analyzer MUST include every directly-changed spec id
  in the blast radius, tagged with reason `direct`, regardless of which file
  within that component's bundle changed.
- **R-IMPACT-002** — For a changed component whose `interface.md` content is
  byte-identical to the prior commit, the analyzer MUST NOT include that
  component's dependents in the blast radius on the basis of that change
  alone — a change confined to `spec.md` (Purpose/Scope/Definitions/Behavior),
  `constraints.md`, or `acceptance.md` is internal and MUST NOT propagate.

  **This distinction was not previously specified anywhere in
  `notes/initial-ideas.md` or `SPEC_GUIDELINES.md` before this spec was
  written** — D2 states it only as a *sizing heuristic* ("a typical spec
  change stays inside the component's own bundle and does not force an edit
  to a depended-upon `interface.md`"), not as an executable rule for this
  component. This requirement is the first place it becomes a real, testable
  behavior rather than an aspiration. Flagged for the main thread as a found
  gap, not a restatement of an existing decision.
- **R-IMPACT-003** — For a changed component whose `interface.md` content
  *did* change relative to the prior commit, the analyzer MUST include every
  component with a `depends_on` edge to it, tagged with reason
  `transitive-interface`, naming the upstream component whose interface
  changed.
- **R-IMPACT-004** — For a changed `specs/vars/` declaration, the analyzer
  MUST treat it the same way as a changed `interface.md`: every component
  with a `uses_var` reference to that declaration is included, tagged
  `transitive-var`, naming the changed variable. (A variable's declared type/
  required/sensitivity is itself the contract a component depends on, per
  D12 — there is no reason to treat it more loosely than an interface change.)
- **R-IMPACT-005** — For a changed product capability (a `P-<id>`'s own file,
  including its golden scenarios), the analyzer MUST include every component
  whose `realizes` lists that `P-<id>`, tagged `transitive-capability` — the
  capability's acceptance bar changed, so components claiming to satisfy it
  need re-verification against the new bar even if their own spec files
  didn't change.
- **R-IMPACT-006** — The analyzer's output MUST be a pure function of
  (changed spec ids, corpus state at the commit being analyzed) — no model
  calls, no network access, no dependence on wall-clock time or execution
  order.
- **R-IMPACT-007** — If the corpus has not passed `spec-linter` cleanly (any
  `fail`-severity finding present, including an unresolved cycle or a
  dangling reference anywhere in the graph, not only in the changed specs),
  the analyzer MUST fail closed — report a precondition error and compute no
  blast radius — rather than attempt a best-effort traversal over a graph it
  cannot trust.

## Interfaces

See `interface.md`.

## Data

See `interface.md` (`BlastRadiusReport` schema).

## Acceptance criteria

See `acceptance.md`.

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
