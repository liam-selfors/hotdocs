# AC-PROV-003

Covers: R-PROV-003
Kind: compiled

```gherkin
Given reported versions from cache-manager, criterion-compiler, and
  license-scanner
When write_provenance runs
Then gate_versions contains exactly those three reported values, unmodified
```
