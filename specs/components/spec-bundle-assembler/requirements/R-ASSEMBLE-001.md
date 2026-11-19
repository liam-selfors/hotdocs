# R-ASSEMBLE-001

**R-ASSEMBLE-001** — The bundle MUST include the target component's own
  `component.md`, everything under `requirements/`, every `.md` file
  under `interface/` and its subdirectories (`data/`, `guarantees/`,
  `assets/`, the last as `R-ASSEMBLE-016` reads it), and
  `constraints.md`. It MUST NOT include anything under `acceptance/`: a
  generator that sees its criteria overfits to their assertions instead
  of implementing the requirements (`SPEC_GUIDELINES.md` §6).

  **The target's `component.md` excludes its own `## Rationale`,
  `## Open questions` and `## Change log` sections** (`D69`): they
  explain past decisions, not what to build, as `R-ASSEMBLE-002`
  already holds for dependencies. Its other sections are kept.
