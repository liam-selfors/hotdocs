# R-LINT-023

**R-LINT-023** — The linter MUST additionally check each individual file
  under `requirements/` and `acceptance/` against a per-file word count
  (warn above 250, fail above 500), distinct from R-LINT-012's
  `component_doc_words` aggregate — naming the specific file, not just the
  bundle total. Each such file is meant to be one atomic unit (D1); one
  running long is a signal an aggregate cannot isolate.
