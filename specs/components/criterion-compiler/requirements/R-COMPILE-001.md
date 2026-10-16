# R-COMPILE-001

**R-COMPILE-001** — The compiler MUST recognize only the fixed, published
  step-phrase grammar (`specs/architecture/step-phrase-grammar.md`) for
  Given/When/Then steps, and MUST reject — with a specific, located compile
  error, never a best-effort guess — any step that does not match a
  recognized template.
