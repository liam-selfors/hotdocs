# AC-GEN-020

Covers: R-GEN-019
Kind: generated-test

```gherkin
Given a cold-mode SpecBundle and a mock model that records what it
  was sent
When generate is called with that bundle
Then the mock model's recorded input instructs it that any value read
  from a dependency call, including the dependency's own top-level
  return value, must use dual dict-or-attribute access, never a bare
  attribute access alone
```
