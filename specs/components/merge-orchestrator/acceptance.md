---
id: comp-merge-orchestrator-acceptance
title: Merge Orchestrator — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Merge Orchestrator — Acceptance Criteria

All thirteen criteria are `kind: compiled` — tested by mocking every
dependency and asserting on call order/arguments, the same pattern
`verifier-orchestrator` and `cross-model-divergence-checker` already
established for coordination logic. A twelfth component in this corpus
whose entire acceptance set is `compiled` — the capstone data point for
D5's guidance: even the component that sequences every model-calling,
judgment-involving gate in the whole pipeline is, in its own right, fully
deterministic.

### AC-MERGE-001
Covers: R-MERGE-001
Kind: compiled

```gherkin
Given a corpus with a hard-fail spec-linter finding
When run_merge is called
Then the merge is blocked before impact-analyzer or any other component is
  invoked
```

### AC-MERGE-002
Covers: R-MERGE-002
Kind: compiled

```gherkin
Given a lint-clean corpus and one changed spec id
When run_merge is called
Then impact-analyzer is invoked with that id and its result determines
  which components proceed
```

### AC-MERGE-003
Covers: R-MERGE-003
Kind: compiled

```gherkin
Given a component whose spec_bundle_hash matches a cache-manager entry
When run_merge is called
Then generator, verifier-orchestrator, cross-model-divergence-checker,
  license-scanner, and secret-scanner are never invoked for that component
```

### AC-MERGE-004
Covers: R-MERGE-004
Kind: compiled

```gherkin
Given a cache miss for an impacted component
When run_merge is called
Then spec-bundle-assembler, generator, and verifier-orchestrator are
  invoked in that order for it
```

### AC-MERGE-005
Covers: R-MERGE-005
Kind: compiled

```gherkin
Given a mock generator/verifier-orchestrator pair where the first sample
  fails and the second passes, with k=3
When run_merge is called
Then generator is called exactly twice, and the recorded sample_index is
  the second attempt's
```

### AC-MERGE-006
Covers: R-MERGE-006
Kind: compiled

```gherkin
Given a mock verifier-orchestrator that always returns fail, with k=2
When run_merge is called
Then generator is called exactly twice and the component's merge is blocked
```

### AC-MERGE-007
Covers: R-MERGE-007
Kind: compiled

```gherkin
Given cross_model_divergence_check disabled and fallback_standby_build
  disabled for a component
When run_merge is called
Then cross-model-divergence-checker is never invoked for that component
```

### AC-MERGE-008
Covers: R-MERGE-008
Kind: compiled

```gherkin
Given any impacted component, regardless of any toggle's state
When run_merge is called
Then license-scanner and secret-scanner are both invoked for it
```

### AC-MERGE-009
Covers: R-MERGE-009
Kind: compiled

```gherkin
Given generation, verification, and both scans have completed for a
  component
When run_merge is called
Then provenance-writer is invoked for that component only after all of them
  have produced results
```

### AC-MERGE-010
Covers: R-MERGE-010
Kind: compiled

```gherkin
Given provenance-writer has completed for every impacted component
When run_merge is called
Then corpus-graph-builder and review-packet-builder are invoked exactly
  once each, not once per component
```

### AC-MERGE-011
Covers: R-MERGE-011
Kind: compiled

```gherkin
Given one impacted component that exhausted retries and another that
  passed cleanly
When run_merge is called
Then the overall merge is blocked, with block_reasons naming the failed
  component
```

### AC-MERGE-012
Covers: R-MERGE-012
Kind: compiled

```gherkin
Given a merge that is not blocked
When run_merge completes
Then specs/, gen/, and verification/ are committed together in one
  squashed commit
```

### AC-MERGE-013
Covers: R-MERGE-013
Kind: compiled

```gherkin
Given a successful merge
When its MergeResult is inspected
Then review_packet is present and no field anywhere in MergeResult contains
  a generated-code diff
```
