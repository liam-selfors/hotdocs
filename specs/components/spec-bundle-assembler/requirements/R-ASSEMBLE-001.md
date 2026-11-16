# R-ASSEMBLE-001

**R-ASSEMBLE-001** — The bundle MUST include the target component's own
  `component.md`, everything under `requirements/`, everything under
  `interface/`, and `constraints.md`. It MUST NOT include anything under
  `acceptance/`. This is deliberate, not an oversight: the generation model
  seeing its own acceptance criteria risks overfitting to specific test
  assertions rather than genuinely implementing the normative requirements
  — already implied by `SPEC_GUIDELINES.md` §6 step 2's bundle definition,
  made an explicit, enforced requirement here for the first time.

  **"The target's own `component.md`" excludes that file's own
  `## Rationale`, `## Open questions`, and `## Change log` sections**
  (`D69`, measured: 15-60% of a real component.md's body, depending on
  the component). `R-ASSEMBLE-002` already applies "a dependent needs
  the contract, not the internal rationale" to every *dependency* this
  bundle includes; this closes the one place that same principle was
  never applied to the target itself, even though these three sections
  explain *why* past decisions were made, not what the model must
  build. `Purpose`/`Scope`/`Definitions`/the `Behavior`/`Interfaces`/
  `Data`/`Acceptance criteria`/`Non-functional constraints` pointer
  text are unaffected — unlike a dependency's `component.md`, the
  target's own Scope and Definitions genuinely describe what to build,
  not just its public contract.
