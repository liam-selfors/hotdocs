# AC-TRACK-005

Covers: R-TRACK-005
Kind: generated-test

```gherkin
Given a merge attempt where every real gate passes, and write_tracking_record
  itself raises an error (e.g. an unwritable .hotdocs/ directory)
When run_merge completes
Then the merge still succeeds and commits normally — the tracking write
  failure has no effect on the merge's own outcome
```
