# AC-CACHE-009

Covers: R-CACHE-003
Kind: compiled

```gherkin
Given two concurrent put calls for the same cache key with two different,
  independently-valid result payloads (the case G-CACHE-001 permits for a
  gate whose own constraints.md scopes determinism narrowly)
When both complete
Then a subsequent get for that key returns exactly one of the two
  payloads, whole and byte-identical to one of the writes — never a
  merge of both, never a partial write of either
```
