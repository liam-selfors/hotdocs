# AC-LICENSE-002

Covers: R-LICENSE-002
Kind: generated-test

```gherkin
Given gen/<component>/ content with no match against the reference corpus
When scan(component_id, repo_root) is called
Then it returns a LicenseScanResult with evaluated true, blocked false,
  matches [] and a numeric similarity_score, and main with --format=json
  prints that same record
```
