# AC-VERIFY-016

Covers: R-VERIFY-014
Kind: generated-test

```gherkin
Given a candidate of one short function whose loop
  `while i < x: i = i + 1` has a mutant that never terminates, and one
  generated test covering it
When verify runs
Then it returns within ten seconds and that mutant counts as killed
```
