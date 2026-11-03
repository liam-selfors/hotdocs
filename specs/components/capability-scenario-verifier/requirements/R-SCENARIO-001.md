# R-SCENARIO-001

**R-SCENARIO-001** — Given a blast-radius component-id set, MUST
  determine every product capability whose `realizes`-set intersects it
  (`R-SCENARIO-002`) and run each one's capability scenarios against the
  real, fully assembled `gen/` output — not a prediction. Each scenario
  is dispatched by its declared `kind` — `compiled` via
  `criterion-compiler`, `generated-test` via `test_author`, `llm-judge`
  via `judge` — with no new dispatch machinery, and `kind` is never
  reinterpreted. For `compiled` and `generated-test`, dispatch means
  producing a test **and running it** (`R-SCENARIO-005`): a scenario
  passes only if that run passes.

  **Where scenarios live** (`D59`): there is no `specs/capabilities/`
  directory. A capability's scenarios are `### CS-<id>` sections inside
  its own `specs/product/<name>.md` (`SPEC_GUIDELINES.md` §3.1), each
  with `Covers:`, `Kind:`, and a Gherkin block — a component's
  `acceptance/` file shape, nested in one file.

  **`compiled` MUST use `criterion-compiler`'s `compile_criterion`**
  (`R-COMPILE-012`), never its directory-scanning `compile`, with
  `surface=None`: a capability scenario is black-box against the whole
  system, so a step still referencing a function or type is a located
  compile error, never silently skipped.

  The report carries one entry **per scenario**, each with `id`,
  `kind`, and `result`; an `llm-judge` entry that dispatched also
  carries `rationale` (`SPEC_GUIDELINES.md` §5). It is keyed by `P-id`,
  never by component, so `provenance-tracker` can report it separately
  (`R-TRACK-010`). A capability's `overall` is `"fail"` if any scenario
  failed, else `"skipped"` if it has scenarios and all were skipped,
  else `"pass"` — and `"fail"` if it has no scenarios at all, since a
  capability that verifies nothing never passes.
