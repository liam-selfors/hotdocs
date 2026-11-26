# R-SIZE-003

**R-SIZE-003** — The linter MUST additionally check each individual file
  under `requirements/` and `acceptance/` against a per-file word count
  (warn above 250, fail above 500), distinct from R-SIZE-001's
  bundle aggregates — naming the specific file, not just the
  bundle total. Each such file is meant to be one atomic unit (D1); one
  running long is a signal an aggregate cannot isolate.
