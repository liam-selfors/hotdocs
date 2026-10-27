# R-ASSIST-006

**R-ASSIST-006** — This component's output MUST NOT gate anything. It
  MUST NOT be read by `provenance-tracker`'s `check_readiness` or
  appear in any component's `depends_on` in a way that could influence
  a pass/fail decision, and its result MUST have no mechanism by which
  it can block a merge — advisory only, by construction, not by
  developer discipline.
