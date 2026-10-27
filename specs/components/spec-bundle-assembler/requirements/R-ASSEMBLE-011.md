# R-ASSEMBLE-011

**R-ASSEMBLE-011** — For each id in the component's `depends_on`, the
  bundle MUST also include a mechanically-derived usage card as
  `dependency_usage[id]`: that dependency's real, currently-importable
  module path, and — for each public top-level symbol its real
  `gen/<dependency>/` code actually defines — its signature and the
  first line of its docstring. No model call; derived by introspecting
  the dependency's own real, already-verified code (`inspect`-level
  facts: callable, signature, docstring — never source text, never
  anything from `acceptance/`).

  **Absent (an empty string) for a dependency with no real code yet** —
  the same graceful-degradation posture `component_provenance` already
  takes for a component with no `.provenance.json` (`R-GQE-005`): a
  spec-only dependency has nothing real to introspect, and that is
  expected state, not an error.

  **A `sealed` dependency's real code lives at its declared
  `source_path`, never under `gen/<dependency>/`** (`D60`) — checked
  first, against that dependency's own `component.md` frontmatter,
  before falling back to the normal `gen/<dependency>/` location.
  Missing this distinction silently degraded every sealed dependency's
  usage card to empty, indistinguishable from "no real code yet" —
  found only once a real dependent (`capability-scenario-verifier`)
  needed real usage info for a real sealed dependency
  (`criterion-compiler`) for the first time.

  **Requires the dependency to already have been (re)generated before
  the dependent's bundle is assembled** — whoever drives generation
  across more than one component in the same pass MUST do so in
  dependency order (dependencies before dependents), never an arbitrary
  or fully parallel order across an edge that crosses this boundary
  (`merge-orchestrator`'s own `R-MERGE-023`). `R-ASSEMBLE-006`'s
  determinism requirement is unaffected, only widened in scope exactly
  as `R-ASSEMBLE-008`'s `hint_code` already treats `gen/` content as
  fair game for a component's own history — this is the same idea
  applied one edge further, to a dependency's `gen/` content instead of
  the dependent's own.

  **Deliberately one-directional — a dependency's bundle MUST NOT
  include anything about how its dependents use it.** Feeding real
  call-site usage back toward a dependency being regenerated was
  considered and rejected: it would reintroduce a cycle into what
  `depends_on` otherwise keeps acyclic (a dependency's regeneration
  could invalidate the very usage it was just shaped around, forcing
  dependents to regenerate again, which could change usage again), and
  it would let accumulated calling patterns steer a dependency's real
  behavior instead of its own normative `interface/` contract — the
  same spec-drift failure mode this corpus has already spent real
  effort catching elsewhere. If a dependent's real need reveals a dependency's
  contract is genuinely missing something, that is a human-reviewed
  `interface/` spec change (flowing through `impact-analyzer`'s blast
  radius the normal way), never an input to a generation prompt.
