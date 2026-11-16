# AC-GEN-016

Covers: R-GEN-015
Kind: generated-test

```gherkin
Given a cold-mode SpecBundle and a mock model that records what it
  was sent
When generate is called with that bundle
Then the mock model's recorded input instructs it to lay out its
  output as a flat module or a package directly under gen/<component>/,
  never a deeper src/-style layout
```
