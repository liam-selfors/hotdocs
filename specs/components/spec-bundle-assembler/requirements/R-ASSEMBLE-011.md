# R-ASSEMBLE-011

**R-ASSEMBLE-011** — For each id in the component's `depends_on`, the
  bundle MUST also include a mechanically-derived usage card as
  `dependency_usage[id]`: that dependency's module name and the
  directory it is loaded from, relative to `repo_root` with a trailing
  `/` (`gen/bar/`, or a sealed dependency's `source_path`), and — for each
  public top-level function or class its real module defines, by sorted
  name — its name, its `inspect.signature` text, and the first line of
  its docstring; one whose signature `inspect` cannot read (an exception
  class, say) is left out. No model call; derived by introspecting
  the dependency's own real, already-verified code (`inspect`-level
  facts: callable, signature, docstring — never source text, never
  anything from `acceptance/`).

  **An empty string for a dependency with no real code yet**: expected
  state, not an error.

  **A `sealed` dependency's real code lives at its declared
  `source_path`, never under `gen/<dependency>/`** (`D60`): its card is
  built from `source_path` only, and is `""` when nothing is there.

  **Requires the dependency to already have been (re)generated before
  the dependent's bundle is assembled** — a developer running
  `hotdocs generate` across more than one component in the same change
  MUST do so in dependency order, dependencies before dependents
  (`D86`, `D91`, `D93`).

  **Deliberately one-directional — a dependency's bundle MUST NOT
  include anything about how its dependents use it.**
