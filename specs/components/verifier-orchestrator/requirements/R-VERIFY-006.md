# R-VERIFY-006

**R-VERIFY-006** — For `generated-test`-kind criteria, this component MUST
  compute and report the mutation score, and the overall verdict MUST be
  `fail` if it falls below the published bar (80% general / 90%
  freeform-derived, `SPEC_GUIDELINES.md` §5).

  **A single score for the whole component, a union across all of its
  own `generated-test` criteria's test files — never an average of
  narrower, per-criterion-isolated scores** (`D124`): generate each
  mutant once, against the whole candidate module; a mutant counts as
  killed if *any* of the component's own `generated-test` criteria's
  test files fails against it, never only the one criterion a score
  happens to be attributed to. `VerificationReport.mutation_score` is
  documented as exactly one number per component (`interface/data/
  VerificationReport.md`), never one per criterion — a criterion whose
  own Gherkin scope covers only one of several functions in a
  multi-function module has no way to kill a mutant living in a
  sibling function, and being scored against it anyway as if it could
  is not a real quality signal.

  **Found only once a genuinely multi-function component
  (`provenance-tracker`, three behaviorally distinct entry points) had
  its own real mutation score computed for the first time** (`D124`):
  scored in isolation per criterion and averaged, the aggregate was
  consistently near-zero across every real attempt regardless of test
  quality — no single criterion's test could ever kill a mutant
  outside its own narrow scope, so the average was structurally
  depressed by the module's own shape, not by anything a better test
  could fix.
