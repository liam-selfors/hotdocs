# AC-ASSEMBLE-021

Covers: R-ASSEMBLE-007
Kind: generated-test

```gherkin
Given the library's project-kind asset fixture
When assemble runs for comp-foo, then again after
  the fixture adapter's "Generator guidance text." becomes "Other text."
Then the two spec_bundle_hash values differ

When assemble runs, then again after
  interface/assets/app.js.md's "double" becomes "triple"
Then the two spec_bundle_hash values differ
```
