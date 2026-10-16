# AC-LICENSE-002

Covers: R-LICENSE-002
Kind: compiled

```gherkin
Given gen/<component>/ content with no match against the reference corpus
When license-scan runs
Then a LicenseScanResult is still written into the provenance manifest,
  recording a clean result rather than omitting one
```
