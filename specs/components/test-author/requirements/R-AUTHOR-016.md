# R-AUTHOR-016

**R-AUTHOR-016** — `author_test` MUST treat every `CriterionBundle`
  field access as optional: a bundle (dict or object) missing a field
  — `dependency_interfaces` above all — MUST read as if that field
  were absent (empty/`None`), never raise `AttributeError`/`KeyError`
  (`D94`).
