# R-ASSEMBLE-009

**R-ASSEMBLE-009** — MUST also expose a narrower assembly entry point
  producing a `CriterionBundle` — one acceptance criterion's own text, its
  covered requirement's text, the target component's `interface/` content,
  and the glossary — for `test-author`'s use. A `CriterionBundle` MUST NOT
  include the target component's `gen/<component>/` content, any other
  file under `requirements/`, or `constraints.md` — narrower than the
  `SpecBundle` R-ASSEMBLE-001–008 describe, not a variant of it, because
  `test-author`'s independence requirement (its own R-AUTHOR-002) depends
  on it seeing *less* than `generator` sees, not the same bundle with
  something added.
