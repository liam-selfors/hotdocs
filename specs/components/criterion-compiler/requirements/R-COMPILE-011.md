# R-COMPILE-011

**R-COMPILE-011** — The compiler's work MUST be structured as two distinct
  phases: **parse+bind** (matching steps against the step-phrase grammar
  and resolving references against the target component's `interface/`
  contract — entirely target-independent, the same for every `--target`
  value) and **emit** (turning the bound, target-independent result into
  literal source text for one specific test framework/language). No rule
  in this spec, `R-COMPILE-001` through `010` included, MUST depend on
  which `--target` is selected — those rules govern parse+bind only.

  For v1, exactly one emitter MUST be implemented: `pytest` (Python), the
  only accepted `--target` value. The compiler MUST reject any other
  `--target` value with a specific usage error (exit code `2`, naming the
  unsupported value) — never a silent fallback to `pytest` and never a
  best-effort guess at an unimplemented target, the same no-silent-guessing
  discipline `R-COMPILE-001` already applies to unrecognized steps.
