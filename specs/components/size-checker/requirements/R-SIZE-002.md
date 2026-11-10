# R-SIZE-002

**R-SIZE-002** — The linter MUST emit a distinct warning when two or more
  of R-SIZE-001's size-cap dimensions are over their *warn* threshold for
  the same component at once — naming which dimensions and their current
  values, and pointing at `SPEC_GUIDELINES.md` §4's decomposition-signal
  guidance. Keyed off *warn*, it surfaces the signal before a hard-fail
  forces the question; it MUST NOT itself ever hard-fail.
