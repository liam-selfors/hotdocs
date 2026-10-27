# AC-TRACK-009

Covers: R-TRACK-009
Kind: generated-test

```gherkin
Given changed_ids naming one changed component, impact-analyzer
  reporting a blast radius of two components, and provenance-checker
  reporting a hit for one and a miss for the other
When check_readiness is called with those changed_ids
Then the report's scope is blast-radius, its components map has
  exactly those two entries, and the missing one is named in
  not_ready_reasons

Given no changed_ids
When check_readiness is called
Then every component under specs/components/ is checked, and the
  report's scope is whole-corpus
```
