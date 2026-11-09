# AC-CACHE-011

Covers: R-CACHE-006
Kind: generated-test

```gherkin
Given an empty repo_root
When main(["stats", "--repo-root=<repo_root>"]) runs
Then it returns 0 and prints {"entry_count": 0}

Given two entries put under repo_root with different keys, and one key
  put twice
When main(["stats", "--repo-root", "<repo_root>"]) runs
Then it prints {"entry_count": 2}
```
