# AC-TRACK-003

Covers: R-TRACK-003
Kind: generated-test

```gherkin
Given three sequential merge attempts
When all three complete
Then three files exist under .hotdocs/tracking/, each named with an
  ISO-8601-prefixed attempt_id, and sorting the filenames lexicographically
  produces the same order the attempts actually ran in
```
