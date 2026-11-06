# AC-TRACK-012

Covers: R-TRACK-012
Kind: generated-test

Any faked provenance-checker provides current_sealed_key (returning None,
so every component here is generated), current_provenance_key,
check_provenance, and check_sealed_provenance (`interface/library.md`).

```gherkin
Given a dict-shaped (never object-shaped) fake provenance-checker
  result and a dict-shaped fake impact-analyzer impacted entry
When check_readiness runs over that scope
Then it reads hit/component_id/etc. correctly from the dict shape
  and does not raise AttributeError
```
