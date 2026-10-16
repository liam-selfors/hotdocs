# R-IMPACT-002

**R-IMPACT-002** — For a changed component whose `interface.md` content is
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
