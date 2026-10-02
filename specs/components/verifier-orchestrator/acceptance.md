---
id: comp-verifier-orchestrator-acceptance
title: Verifier Orchestrator — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Verifier Orchestrator — Acceptance Criteria

All eight criteria are `kind: compiled` — this component coordinates
checking mechanisms (some of which involve judgment or external calls), but
the coordination itself is deterministic dispatch-and-record logic, testable
by mocking `criterion-compiler` and the judge callable. A fourth component
in this corpus whose entire acceptance set is `compiled`.

### AC-VERIFY-001
Covers: R-VERIFY-001
Kind: compiled

```gherkin
Given a component with one compiled-kind acceptance criterion and a mock
  criterion-compiler
When verify runs
Then the mock compiler is invoked for that criterion and its pass/fail
  result appears in the report under that criterion's id
```

### AC-VERIFY-002
Covers: R-VERIFY-002
Kind: compiled

```gherkin
Given a component with one generated-test-kind acceptance criterion and its
  already-generated test file present in verification/<component>/
When verify runs
Then that test is executed against gen/<component>/ and its pass/fail
  result appears in the report
```

### AC-VERIFY-003
Covers: R-VERIFY-003
Kind: compiled

```gherkin
Given a component with one llm-judge-kind acceptance criterion
When verify runs with no judge configured
Then that criterion's result is skipped, with a null rationale, and verify
  does not call a model itself to produce that result
```

### AC-VERIFY-004
Covers: R-VERIFY-004
Kind: compiled

```gherkin
Given a component whose gen/<component>/ public interface does not match
  interface.md
When verify runs
Then interface_drift is true and the overall verdict is fail
```

### AC-VERIFY-005
Covers: R-VERIFY-005
Kind: compiled

```gherkin
Given a component where every compiled and generated-test criterion passes,
  interface_drift is false, and the only llm-judge criterion is skipped
When verify runs
Then the overall verdict is pass — a skipped finding alone never causes fail
```

### AC-VERIFY-006
Covers: R-VERIFY-006
Kind: compiled

```gherkin
Given a component with a generated-test-kind criterion whose mutation score
  is below the published bar
When verify runs
Then the overall verdict is fail, citing the mutation-score shortfall
```

### AC-VERIFY-007
Covers: R-VERIFY-007
Kind: compiled

```gherkin
Given any component
When verify runs
Then exactly one VerificationReport is produced containing per-criterion
  results, mutation_score, interface_drift, and overall
```

### AC-VERIFY-008
Covers: R-VERIFY-008
Kind: compiled

```gherkin
Given unchanged gen/<component>/ and acceptance.md, and a judge callable
  that returns the same result every time it is called
When verify runs twice
Then the two VerificationReports are identical
```
