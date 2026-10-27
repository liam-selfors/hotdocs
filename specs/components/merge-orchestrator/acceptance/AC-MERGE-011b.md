# AC-MERGE-011b

Covers: R-MERGE-011
Kind: generated-test

```gherkin
Given a sealed component whose characterization-test verification
  (R-MERGE-015) fails, and no other component in the blast radius has any
  failure
When run_merge is called
Then the overall merge is blocked, with block_reasons naming the sealed
  component — not silently passing just because no retry was exhausted
```
