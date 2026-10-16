# AC-MERGE-014

Covers: R-MERGE-014
Kind: compiled

```gherkin
Given a blast radius of two components, both of which have regenerated and
  passed their own per-component verification, and one product capability
  whose realizes-set includes both
When run_merge is called
Then that capability's golden scenarios are run against the real assembled
  gen/ output, dispatched via criterion-compiler/test_author/judge exactly
  as verifier-orchestrator's own criteria are, and a failure there blocks
  the overall merge independent of either component's own verification
  result
```
