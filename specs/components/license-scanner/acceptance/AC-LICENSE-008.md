# AC-LICENSE-008

Covers: R-LICENSE-001
Kind: generated-test

```gherkin
Given gen/<component>/ content that shares an 8-token run with a
  reference-corpus entry but no 9-token run
When license-scan runs
Then that shared run contributes no matching window-hash — confirming
  the window size is exactly 9 tokens, not 8 or some other nearby value
```
