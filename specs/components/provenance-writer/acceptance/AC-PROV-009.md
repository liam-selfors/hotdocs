# AC-PROV-009

Covers: R-PROV-009
Kind: compiled

```gherkin
Given cache_hit is true and a matching prior commit's manifest exists
When write_provenance runs
Then verification_report, license_scan, and secret_scan are copied
  verbatim from that prior manifest, not freshly computed
```
