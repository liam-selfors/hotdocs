# AC-PROV-007

Covers: R-PROV-007
Kind: compiled

```gherkin
Given a clean LicenseScanResult and a clean SecretScanResult
When write_provenance runs
Then both license_scan and secret_scan are present in the manifest, even
  though neither flagged anything
```
