# R-VERIFY-011

**R-VERIFY-011** — The `VerificationReport` MUST include
  `requirement_results`: one `pass`/`fail` entry per `R-id` the
  component declares, `pass` only if **every** criterion whose
  `Covers:` names it is `pass`, `fail` if any is `fail` or `skipped`.

  It MUST contain **only** `R-id` keys and `pass`/`fail` values
  (R-ASSEMBLE-001).
