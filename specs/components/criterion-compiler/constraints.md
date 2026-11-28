# Criterion Compiler — Non-Functional Constraints

- **No network access, no model calls, ever.**
- **Performance.** Compiling one component's `acceptance/` against its
  `interface/` MUST complete in under 500ms on reference hardware.
- **Characterization coverage.** The hand-authored reference fixture suite
  (`acceptance/`+`interface/` content pairs with known-correct expected
  output, living in `verification/criterion-compiler/`) MUST cover every
  entry in the step grammar (`specs/architecture/step-phrase-grammar.md`)
  and every error path (R-COMPILE-001, 002, 007) — this is the actual trust
  mechanism §8 requires of a sealed component, and for this component
  specifically, it is the *only* thing standing behind the entire `compiled`
  tier's credibility. It MUST NOT be allowed to lag the grammar in practice
  the way it's easy for hand-written tests to lag a hand-written
  implementation.
