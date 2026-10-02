---
id: comp-criterion-compiler-constraints
title: Criterion Compiler — Non-Functional Constraints
status: draft
owners: [pipeline-team]
---

# Criterion Compiler — Non-Functional Constraints

- **Determinism.** The same `acceptance.md` + `interface.md` pair MUST always
  compile to byte-identical output. Required for D13's cache-key correctness
  — same obligation `spec-linter` carries, for the same reason.
- **No network access, no model calls, ever.** Structurally enforced, not
  just by convention: this is the strongest possible trust tier — the one
  component in the system where "no model in the loop" is not merely
  preferred (as `compiled`-kind criteria generally are) but load-bearing for
  the whole `compiled` mechanism's trust argument.
- **Performance.** Compiling one `acceptance.md` against its `interface.md`
  MUST complete in under 500ms on reference hardware — faster than
  `spec-linter`'s 2s budget, since this operates on a single file pair with no
  corpus-wide graph walk.
- **Idempotent on unchanged input.** Recompiling unchanged input MUST NOT
  touch already-written output files (R-COMPILE-009) — avoids spurious diffs
  that would otherwise defeat D11's cache-hit comparison.
- **Characterization coverage.** The hand-authored reference fixture suite
  (acceptance.md/interface.md pairs with known-correct expected output,
  living in `verification/criterion-compiler/`) MUST cover every entry in the
  step grammar (`interface.md`) and every error path (R-COMPILE-001, 002,
  007) — this is the actual trust mechanism §9 requires of a sealed
  component, and for this component specifically, it is the *only* thing
  standing behind the entire `compiled` tier's credibility. It MUST NOT be
  allowed to lag the grammar in practice the way it's easy for hand-written
  tests to lag a hand-written implementation.
