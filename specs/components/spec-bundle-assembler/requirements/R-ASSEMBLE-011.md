# R-ASSEMBLE-011

**R-ASSEMBLE-011** — For each id in the component's `depends_on`, the
  bundle MUST also include a mechanically-derived usage card as
  `dependency_usage[id]`: that dependency's module name and the
  directory it is loaded from, relative to `repo_root` with a trailing
  `/` (`gen/bar/`, or a sealed dependency's `source_path`), and — for each
  public top-level callable its real code defines — its name, its
  `inspect.signature` text, and the first line of its docstring. No model call; derived by introspecting
  the dependency's own real, already-verified code (`inspect`-level
  facts: callable, signature, docstring — never source text, never
  anything from `acceptance/`).

  **Absent (an empty string) for a dependency with no real code yet** —
  the same graceful-degradation posture `component_provenance` already
  takes for a component with no `.provenance.json` (`R-GQE-005`): a
  spec-only dependency has nothing real to introspect, and that is
  expected state, not an error.

  **A `sealed` dependency's real code lives at its declared
  `source_path`, never under `gen/<dependency>/`** (`D60`): its card is
  built from `source_path` only, and is `""` when nothing is there.

  **Requires the dependency to already have been (re)generated before
  the dependent's bundle is assembled** — a developer running
  `hotdocs generate` across more than one component in the same change
  MUST do so in dependency order, dependencies before dependents
  (`D86`, `D91`, `D93`).

  **Deliberately one-directional — a dependency's bundle MUST NOT
  include anything about how its dependents use it.** Feeding real
  call-site usage back toward a dependency being regenerated was
  considered and rejected: it would reintroduce a cycle into what
  `depends_on` otherwise keeps acyclic (a dependency's regeneration
  could invalidate the very usage it was just shaped around, forcing
  dependents to regenerate again, which could change usage again), and would let calling patterns steer a dependency's behavior instead of
  its `interface/` contract. A missing contract is an `interface/` spec
  change, never a prompt input.
