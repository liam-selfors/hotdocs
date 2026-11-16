# AC-ASSEMBLE-007

Covers: R-ASSEMBLE-007
Kind: generated-test

```gherkin
Given the library's test fixture, with comp-bar depending on comp-foo and
  legacy/foo/foo.py holding def foo(x): return 2 * x
When assemble runs for comp-bar in cold mode
Then spec_bundle_hash equals "sha256:" plus the SHA-256 hex digest of the
  stream R-ASSEMBLE-007 defines, which the test builds itself from those
  files

Given the same corpus
When legacy/foo/.provenance.json is written with any content and assemble
  runs for comp-bar again
Then spec_bundle_hash is unchanged

Given the same corpus
When legacy/foo/foo.py gains a line and assemble runs for comp-bar again
Then spec_bundle_hash changes
```
