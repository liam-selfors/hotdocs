---
id: comp-criterion-compiler-acceptance
title: Criterion Compiler — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Criterion Compiler — Acceptance Criteria

Every criterion below is `kind: generated-test`, not `compiled` — using the
compiler to verify the compiler would prove nothing about correctness
independent of the compiler's own bugs (see `spec.md`'s circularity note).
An agent writes these tests from this prose, with no access to the
hand-maintained implementation at `pipeline/criterion-compiler/` — the same
independence argument `generated-test` normally makes between an agent's test
and an agent's *generated* code, just applied here between an agent's test
and a *human's* code, which is at least as independent.

### AC-COMPILE-001
Covers: R-COMPILE-001
Kind: generated-test

```gherkin
Given an acceptance.md containing a step that does not match any recognized
  template in the step grammar
When compile-criteria runs against it
Then the CompileReport marks that criterion status: error, naming the exact
  file, line, and the unmatched step text — not a silent skip
```

### AC-COMPILE-002
Covers: R-COMPILE-002
Kind: generated-test

```gherkin
Given an acceptance.md step that references a function name not declared in
  the paired interface.md
When compile-criteria runs
Then the CompileReport marks that criterion status: error, naming the
  unresolved reference
```

### AC-COMPILE-003
Covers: R-COMPILE-003
Kind: generated-test

```gherkin
Given a fixed acceptance.md/interface.md pair
When compile-criteria runs against it twice, in two separate processes
Then both runs produce byte-identical output files
```

### AC-COMPILE-004
Covers: R-COMPILE-004
Kind: generated-test

```gherkin
Given a criterion AC-FOO-003 with Covers: R-FOO-003
When it compiles successfully
Then the emitted test file contains R-FOO-003 as traceable metadata (e.g. a
  comment or decorator), not just an opaque test name
```

### AC-COMPILE-005
Covers: R-COMPILE-005
Kind: generated-test

```gherkin
Given an acceptance.md containing one Kind: compiled criterion and one
  Kind: llm-judge criterion
When compile-criteria runs
Then the compiled criterion produces an emitted test file and the llm-judge
  criterion appears in CompileReport.summary.skipped_non_compiled_kind, not as
  an error
```

### AC-COMPILE-006
Covers: R-COMPILE-006
Kind: generated-test

```gherkin
Given a successful compile of a component named "widget"
When the output files are written
Then they are written under verification/widget/compiled/ and nowhere under
  specs/
```

### AC-COMPILE-007
Covers: R-COMPILE-007
Kind: generated-test

```gherkin
Given a step whose literal argument contains text resembling executable code
  (e.g. a shell command or an eval-able expression) inside a quoted string
  literal
When compile-criteria runs
Then the literal is emitted as inert data in the test output, never executed
  during compilation and never emitted as executable glue code
```

### AC-COMPILE-008
Covers: R-COMPILE-008
Kind: generated-test

```gherkin
Given any acceptance.md/interface.md pair, valid or invalid
When compile-criteria runs, observed under a network-disabled sandbox
Then compilation completes (successfully or with a compile error) with no
  outbound network calls of any kind
```

### AC-COMPILE-009
Covers: R-COMPILE-009
Kind: generated-test

```gherkin
Given an unchanged acceptance.md/interface.md pair already compiled once
When compile-criteria runs again against the same --out directory
Then no output file's mtime or content changes
```

### AC-COMPILE-010
Covers: R-COMPILE-010
Kind: generated-test

```gherkin
Given two versions of the compiler where the step grammar has changed between
  them
When each version compiles the same acceptance.md/interface.md pair
Then CompileReport.gate_version differs between the two runs
```
