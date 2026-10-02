---
id: comp-cross-model-divergence-checker-acceptance
title: Cross-Model Divergence Checker — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Cross-Model Divergence Checker — Acceptance Criteria

All nine criteria are `kind: compiled`. This might look surprising for a
component whose whole point is comparing two *model-generated* candidates —
but once both candidates exist and a test suite exists, "do these two
concrete outputs match" is a mechanical equality check, no judgment
involved. The fifth component in this corpus whose entire acceptance set is
`compiled` (after `impact-analyzer`, `cache-manager`,
`spec-bundle-assembler`, `verifier-orchestrator`) — judgment and model
calls happen inside `generator` and (optionally) `llm-judge` criteria this
component merely coordinates, never in this component's own logic.

### AC-XMODEL-001
Covers: R-XMODEL-001
Kind: compiled

```gherkin
Given both toggles disabled and this component invoked anyway
When cross-check runs
Then it reports "not applicable" rather than running either mode
```

### AC-XMODEL-002
Covers: R-XMODEL-002
Kind: compiled

```gherkin
Given a component's canonical gen/<component>/ tree and a second model
  identifier
When cross-check runs
Then a second candidate is produced from the same spec_bundle_hash with the
  second model, and the canonical tree is unmodified afterward
```

### AC-XMODEL-003
Covers: R-XMODEL-003
Kind: compiled

```gherkin
Given a second candidate has been produced
When cross-check runs
Then verifier-orchestrator is invoked against it using the same
  acceptance.md as the canonical build
```

### AC-XMODEL-004
Covers: R-XMODEL-004
Kind: compiled

```gherkin
Given a second candidate whose verdict is pass, in divergence mode
When cross-check runs
Then the same test inputs are run against both candidates and their outputs
  are compared
```

### AC-XMODEL-005
Covers: R-XMODEL-005
Kind: compiled

```gherkin
Given two candidates that both pass verification but produce different
  outputs for the same input, in divergence mode
When cross-check runs
Then diverged is true, divergence_detail names the specific criterion
  involved, and the result is merge-blocking (exit code 1)
```

### AC-XMODEL-006
Covers: R-XMODEL-006
Kind: compiled

```gherkin
Given a second candidate whose verdict is fail, in divergence mode
When cross-check runs
Then the result is logged as a second-model capability gap, diverged is
  false (not evaluated), and the result is not merge-blocking (exit code 0)
```

### AC-XMODEL-007
Covers: R-XMODEL-007
Kind: compiled

```gherkin
Given fallback_standby_build enabled and cross_model_divergence_check
  disabled
When cross-check runs in standby-only mode
Then a verified second candidate is produced, diverged is null, and no
  output comparison is performed
```

### AC-XMODEL-008
Covers: R-XMODEL-008
Kind: compiled

```gherkin
Given a successfully produced and verified second candidate, in either mode
When its CrossCheckResult is inspected
Then it contains everything D10's fallback-promotion mechanism needs to
  promote it directly, with no additional reconciliation step
```

### AC-XMODEL-009
Covers: R-XMODEL-009
Kind: compiled

```gherkin
Given a second model from the same vendor as the canonical pin
When cross-check runs
Then different_vendor is false, and the run is neither blocked nor flagged
  as an error — it's a recorded fact, not a gate
```
