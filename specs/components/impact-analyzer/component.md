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

Built on the engine named in `specs/architecture/graph-query-engine.md`
(R-IMPACT-009): the corpus graph is loaded directly from spec frontmatter
via DuckDB's `yaml` extension, and transitive propagation is computed via
`duckpgq` graph-pattern queries — this is the first component rebuilt on
that shared engine, not a bespoke traversal implementation.

## Scope

**In scope:** determining, for a given set of changed spec ids, which
components are directly changed and which are transitively impacted because
something they depend on changed in a way that affects their contract.
Distinguishing a dependency's *contract* changing from its *internals*
changing, so an unrelated component's change doesn't force regeneration of
everything downstream of it. Since D16: distinguishing, within the
contract itself, type-level content (`cli.md`/`library.md`/`data/*.md` —
always coarse, always propagates) from behavioral guarantees
(`guarantees/*.md` — narrowable, opt-in, per `depends_on_guarantees`).

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

None. The two originally recorded here are both resolved:

- ~~R-IMPACT-002/003 define contract-change detection as "is `interface.md`
  byte-identical" — blunt~~ — resolved by D15 (one-file-per-unit hashing,
  no semantic diffing needed) and sharpened further by D16: true semantic
  diffing *within* one `interface/` file (e.g. a typo fix in `library.md`'s
  prose still forcing propagation) remains unsolved for `cli.md`/
  `library.md`/`data/*.md` — accepted as safe-but-wasteful, same as
  before — but for behavioral guarantees specifically, D16's
  `interface/guarantees/` + `depends_on_guarantees` narrowing solves the
  *coarser* version of this same problem: a dependent that only cares
  about one guarantee no longer pays for changes to unrelated ones.
- ~~Should `R-IMPACT-004`/`005`'s transitive inclusion cascade further?~~ —
  resolved: stays one-hop, by design, **not** because the residual risk
  was dismissed, but because it's covered by a different, better-suited
  mechanism. One-hop risks a second-order change (e.g., component A's
  *behavior* shifting as a side effect of a var/capability-driven
  regeneration) going uncaught this merge if A's dependents aren't pulled
  in too. D16 closes this two ways: (1) `interface/guarantees/` makes any
  *foreseen* behavioral dependency explicit and propagating, the same
  one-hop mechanism everything else uses — no cascading needed once the
  guarantee itself is visible; (2) `merge-orchestrator`'s golden-scenario
  gate (R-MERGE-014) is the permanent backstop for whatever wasn't
  foreseen, tested against the real regenerated system rather than
  guessed at here. Eager multi-hop cascading from every `transitive-var`/
  `transitive-capability` edge was rejected as the alternative — it would
  trade this bounded, already-covered risk for routinely ballooning the
  blast radius on pure speculation, undermining D13's whole cost-
  containment premise.

## Change log

- Initial draft.
