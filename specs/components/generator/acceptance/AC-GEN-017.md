# AC-GEN-017

Covers: R-GEN-016
Kind: generated-test

```gherkin
Given a hint-mode SpecBundle with no existing cache entry, and a mock
  model that returns valid file content
When generate is called with that bundle
Then the returned result contains the candidate's files, but
  gen/<component>/ is untouched and nothing is written to the cache

Given a hint-mode SpecBundle whose exact spec state already has a
  cached cold-mode result
When generate is called with that bundle
Then the cached result is returned, no model call occurs, and
  gen/<component>/ stays untouched
```
