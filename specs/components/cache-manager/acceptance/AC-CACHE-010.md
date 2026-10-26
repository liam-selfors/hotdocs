# AC-CACHE-010

Covers: R-CACHE-009
Kind: compiled

```gherkin
Given VAR-CACHE-STORE-URL is absent
When put is called for a key and then get is called for the same key
Then get returns the stored result, read back from .hotdocs/cache/,
  with no distinct code path required by the caller
```
