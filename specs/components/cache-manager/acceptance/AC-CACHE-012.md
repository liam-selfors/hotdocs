# AC-CACHE-012

Covers: R-CACHE-009
Kind: generated-test

```gherkin
Given VAR_CACHE_STORE_URL is set to "redis://cache.internal:6379/0"
When a valid result is put under repo_root and get is called for the
  same key
Then get returns Miss, nothing exists under <repo_root>/.hotdocs/cache/,
  and main(["stats", "--repo-root=<repo_root>"]) prints {"entry_count": 0}

Given VAR_CACHE_STORE_URL is set and put receives a payload missing a
  required key for its gate type
Then put still raises the schema-validation error
```
