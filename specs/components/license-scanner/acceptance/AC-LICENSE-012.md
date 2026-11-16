# AC-LICENSE-012

Covers: R-LICENSE-010
Kind: generated-test

```gherkin
Given VAR_LICENSE_CORPUS_PATH unset, and gen/foo/ holding any code
When scan("comp-foo", repo_root) runs
Then evaluated is false, reason is "no-reference-corpus",
  similarity_score and block_threshold are null, matches is [], blocked
  is false, and gate_version is "license_scanner@4.0.0-no-reference-corpus"

Given VAR_LICENSE_CORPUS_PATH set to a corpus file whose entries list
  is empty
When scan runs
Then evaluated is false, reason is "corpus-invalid", and blocked is true

Given VAR_LICENSE_CORPUS_PATH set to a valid corpus with one entry that
  shares no 9-token windows with gen/foo/
When scan runs
Then evaluated is true, reason is null, similarity_score is the number
  0.0 (not null), blocked is false, and gate_version is
  "license_scanner@4.0." followed by the corpus's corpus_version, "+",
  and the first 12 hex digits of the corpus file's SHA-256
```
