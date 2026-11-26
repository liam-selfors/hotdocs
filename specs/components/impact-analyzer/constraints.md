# Impact Analyzer — Non-Functional Constraints

- **Determinism.** Same `(changed_ids, corpus state)` input MUST always
  produce byte-identical output.
- **Performance.** Computing blast radius for a single-digit number of
  changed ids MUST complete in well under 1 second against a corpus with
  hundreds of components.
- **No network access, no model calls.**
- **Fail closed, not best-effort.** Per R-IMPACT-007, an invalid corpus graph
  MUST produce an explicit precondition error, never a partial or
  silently-wrong blast radius.
