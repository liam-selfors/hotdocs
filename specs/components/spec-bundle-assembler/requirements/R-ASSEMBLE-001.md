# R-ASSEMBLE-001

**R-ASSEMBLE-001** — The bundle MUST include the target component's own
  `component.md`, everything under `requirements/`, everything under
  `interface/`, and `constraints.md`. It MUST NOT include anything under
  `acceptance/`. This is deliberate, not an oversight: the generation model
  seeing its own acceptance criteria risks overfitting to specific test
  assertions rather than genuinely implementing the normative requirements
  — already implied by `SPEC_GUIDELINES.md` §6 step 2's bundle definition,
  made an explicit, enforced requirement here for the first time.
