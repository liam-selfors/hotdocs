# AC-LICENSE-007

Covers: R-LICENSE-007
Kind: generated-test

```gherkin
Given content that scans flagged, then the same component's content
  changed so that it scans clean
When the flagged content is restored and scanned again
Then the second scan was not blocked, and the third returns the flagged
  result again from the cache, with the same similarity_score and
  matches
```
