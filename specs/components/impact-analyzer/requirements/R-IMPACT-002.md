# R-IMPACT-002

**R-IMPACT-002** — For a changed component whose `interface/` content
  (the full set of `interface/cli.md`, `interface/library.md`, and every
  file under `interface/data/`, each compared independently — any one
  file's content byte-identical to the prior commit contributes nothing to
  this component's own change, but a file *added or removed* under
  `interface/` counts as changed) is entirely unchanged relative to the
  prior commit, the analyzer MUST NOT include that component's dependents
  in the blast radius on that basis alone — a change confined to
  `component.md` (Purpose/Scope/Definitions), `requirements/`,
  `constraints.md`, or `acceptance/` is internal and MUST NOT propagate.

  **This distinction was not previously specified anywhere in
  `notes/initial-ideas.md` or `SPEC_GUIDELINES.md` before this spec was
  originally written** — D2 states it only as a *sizing heuristic* ("a
  typical spec change stays inside the component's own bundle and does not
  force an edit to a depended-upon interface"), not as an executable rule
  for this component. This requirement is the first place it becomes a
  real, testable behavior rather than an aspiration.

  **D15 update:** originally this rule compared `interface.md` as one
  whole file, hashed byte-for-byte — correct but blunt (a purely cosmetic
  edit anywhere in the file still forced full propagation), and a later
  working session explored section-scoped hashing as a refinement before
  settling on the one-file-per-unit redesign (D15) instead, which achieves
  the same precision — a prose-only edit to, say, `interface/library.md`'s
  explanatory text still counts as that file changing, same as before, but
  a change entirely confined to `requirements/`/`acceptance/`/
  `constraints.md`/`component.md`'s narrative sections no longer touches
  `interface/` at all and so no longer forces propagation. No new parsing
  logic was needed to get this — directory structure already *is* the
  section boundary.
