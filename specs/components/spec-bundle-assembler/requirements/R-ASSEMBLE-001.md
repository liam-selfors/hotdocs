# R-ASSEMBLE-001

**R-ASSEMBLE-001** — The bundle MUST include the target component's own
  `spec.md`, `interface.md`, and `constraints.md`. It MUST NOT include
  `acceptance.md`. This is deliberate, not an oversight: the generation
  model seeing its own acceptance criteria risks overfitting to specific
  test assertions rather than genuinely implementing the normative Behavior
  section — already implied by `SPEC_GUIDELINES.md` §6 step 2's bundle
  definition, made an explicit, enforced requirement here for the first
  time.
