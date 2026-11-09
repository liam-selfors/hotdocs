# AC-CACHE-009

Covers: R-CACHE-003
Kind: generated-test

```gherkin
Given two valid generator results for the same key, built under
  gate_version "generator@1.0.0" with gate_type "generator", whose
  payloads have the same required keys and differ only in files:
  {"a.py": "A"} versus {"b.py": "B"}
When two threads put them concurrently, repeated over 20 trials with a
  fresh repo_root each
Then after each trial get returns a CachedResult whose payload equals
  one of the two payloads exactly, never one with both a.py and b.py
  in files and never a missing or truncated entry
```
