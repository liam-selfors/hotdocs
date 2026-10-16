# AC-LICENSE-001

Covers: R-LICENSE-001
Kind: compiled

```gherkin
Given gen/<component>/ content whose k-gram similarity to the reference
  corpus is at or above the configured block threshold
When license-scan runs
Then blocked is true and the merge is reported as blocked
```
