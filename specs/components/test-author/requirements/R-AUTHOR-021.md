# R-AUTHOR-021

**R-AUTHOR-021** — The prompt MUST instruct that every field read from
  a value the target itself returns (not only a faked dependency's
  data) MUST use dual dict-or-attribute access, never assumed to be
  one shape — this corpus's duck-typing convention (`D94`) means any
  component may return either shape in a given round.

  Found at `D112`: one `provenance-tracker` batch applied dual access
  inconsistently, correctly for one criterion, bare for three others.
