# AC-LICENSE-013

Covers: R-LICENSE-011
Kind: generated-test

```gherkin
Given VAR_LICENSE_CORPUS_PATH naming a file that does not exist
When scan("comp-foo", repo_root) runs
Then evaluated is false, reason is "corpus-unreadable", blocked is true,
  similarity_score is null, and gate_version is
  "license_scanner@4.0.0-corpus-unreadable"

Given a corpus file that is not valid JSON, or is a JSON list, or has
  no "entries" list, or has corpus_version "x", or block_threshold 0
  or 1.5, or an entry whose hashes is not a list, or an entry whose
  risk_tier is "severe"
When scan runs for each
Then each gives evaluated false, reason "corpus-invalid", blocked
  true, and gate_version "license_scanner@4.0.0-corpus-invalid"

Given the same unreadable corpus and VAR_COMPLIANCE_WEBHOOK_URL set,
  with urllib.request.urlopen replaced by a recorder
When scan runs
Then notified is true (the scan blocked) and the recorder received a
  payload containing evaluated false and the reason
```
