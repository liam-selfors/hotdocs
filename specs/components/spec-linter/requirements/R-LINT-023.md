# R-LINT-023

**R-LINT-023** — The linter MUST additionally check each individual file
  under `requirements/` and `acceptance/` against a per-file word count
  (warn above 250, fail above 500), distinct from R-LINT-012's
  `spec_bundle_words` aggregate — naming the specific file, not just the
  bundle total. D15's design intent is that each such file is one atomic,
  single-purpose unit; a single file running long is a direct signal that
  assumption broke down for *that file*, which a bundle-wide aggregate
  alone cannot distinguish from "this component just has a lot of
  ordinary content spread evenly across many files."

  First-pass thresholds (D29), explicitly open to recalibration once more
  of the corpus exists to test them against — unlike R-LINT-012's
  existing dimensions, there was no prior data point to calibrate
  against before this rule existed.
