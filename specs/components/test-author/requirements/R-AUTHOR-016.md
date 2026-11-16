# R-AUTHOR-016

**R-AUTHOR-016** — `author_test` MUST treat every `CriterionBundle`
  field access as optional: a bundle (dict or object) missing a field
  — `dependency_interfaces` above all — MUST read as if that field
  were absent (empty/`None`), never raise `AttributeError`/`KeyError`.
  `CriterionBundle` is duck-typed (`D94`), and this corpus has more
  than one bundle-shaped producer, some narrower than
  `spec-bundle-assembler`'s canonical shape (`R-ASSEMBLE-009`) —
  `author_test` owns that compatibility, not either producer.

  Found once a second producer predated `R-AUTHOR-011` and never
  carried `dependency_interfaces` (`D106`, closed for real by `D119`):
  crashed with a bare `AttributeError`.
