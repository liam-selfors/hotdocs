# AC-MERGE-013

Covers: R-MERGE-013
Kind: compiled

```gherkin
Given a successful merge
When its MergeResult is inspected
Then review_packet is present and no field anywhere in MergeResult contains
  a generated-code diff
```
