# R-LINT-022

**R-LINT-022** — The linter MUST emit a distinct warning when two or more
  of R-LINT-012's size-cap dimensions are over their *warn* threshold for
  the same component at once — naming which dimensions and their current
  values, and pointing at `SPEC_GUIDELINES.md` §4's decomposition-signal
  guidance — rather than leaving a human to notice the correlation across
  separate R-LINT-012 findings themselves.

  Deliberately keyed off *warn*, not hard-fail: the whole point is to
  surface the signal before a hard-fail forces the question, the way D14's
  own `merge-orchestrator` extraction happened only after `component_doc_words`
  had already crossed 4000. This rule MUST NOT itself ever raise a hard
  failure — it is advisory, same severity class as the R-LINT-012 findings
  it correlates, never a merge-blocking condition of its own.
