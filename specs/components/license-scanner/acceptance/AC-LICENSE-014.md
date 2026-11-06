# AC-LICENSE-014

Covers: R-LICENSE-005
Kind: generated-test

```gherkin
Given a stand-in cache-manager holding a result stored under
  gate_version "license_scanner@4.0.0-no-reference-corpus" for gen/foo/'s
  content, and VAR_LICENSE_CORPUS_PATH then set to a valid corpus
  whose corpus_version is 0
When scan("comp-foo", repo_root) runs
Then the stored result is not reused, the scan runs fresh, and
  evaluated is true with gate_version "license_scanner@4.0.0+" followed by
  the first 12 hex digits of the corpus file's SHA-256

Given the reverse: an evaluated result stored under that evaluated
  gate_version, and the variable then unset
When scan runs
Then the stored result is not reused and the result is not evaluated

Given an evaluated result stored for a corpus, and one entry then added
  to the corpus file with corpus_version unchanged
When scan runs
Then the stored result is not reused
```
