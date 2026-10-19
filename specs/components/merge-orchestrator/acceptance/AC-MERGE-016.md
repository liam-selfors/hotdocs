# AC-MERGE-016

Covers: R-MERGE-005
Kind: compiled

```gherkin
Given a mock generator/verifier-orchestrator pair where the first sample
  fails with requirement_results {"R-FOO-001": "pass", "R-FOO-002": "fail"}
When run_merge retries
Then the second generator call's retry_feedback argument is exactly
  ["R-FOO-002"], and the first call's retry_feedback argument was absent
  (no preceding attempt to derive it from)
```
