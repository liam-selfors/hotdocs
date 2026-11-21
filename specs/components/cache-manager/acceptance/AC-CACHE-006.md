# AC-CACHE-006

Covers: R-CACHE-006
Kind: generated-test

```gherkin
Given an entry put under repo_root for CacheKey("sha256:a", "sha256:b",
  "generator@1.0.0", "m") with gate_type "generator" and stored_at
  "2026-01-01T00:00:00Z"
When main(["inspect", "--spec-bundle-hash=sha256:a",
  "--gate-inputs-hash=sha256:b", "--gate-version=generator@1.0.0",
  "--model-pin=m", "--repo-root=<repo_root>"]) runs
Then it returns 0 and prints {"result": "hit", "gate_type": "generator",
  "stored_at": "2026-01-01T00:00:00Z"}, with no "payload" key

Given the same call with --model-pin=other
Then it returns 0 and prints {"result": "miss"}

Given main(["inspect", "--spec-bundle-hash=sha256:a"]), main([]), or
  main(["purge"])
Then each returns 2

Given the full inspect call above with any one of its four hash, version
  or pin flags left out, or with "--model-pin=m" written as "--model=m"
Then each returns 2
```
