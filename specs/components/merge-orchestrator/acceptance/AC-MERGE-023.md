# AC-MERGE-023

Covers: R-MERGE-022
Kind: generated-test

```gherkin
Given run_merge is called with retry_feedback={"comp-foo": ["R-FOO-002"]}
  and comp-bar also in the blast radius with no entry in that mapping
When run_merge processes both components
Then comp-foo's component-gate-runner call receives retry_feedback
  ["R-FOO-002"], and comp-bar's component-gate-runner call receives no
  retry_feedback at all — confirming this component only passes through
  what the caller supplied, never deriving it itself
```
