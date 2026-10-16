# AC-PROV-005

Covers: R-PROV-005
Kind: compiled

```gherkin
Given a VerificationReport with overall "fail"
When write_provenance runs
Then verification_report in the manifest contains that full report, not a
  summary of it
```
