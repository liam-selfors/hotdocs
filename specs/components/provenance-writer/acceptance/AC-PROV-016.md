# AC-PROV-016

Covers: R-PROV-016
Kind: generated-test

```gherkin
Given a ProvenanceInputs whose license_scan_result and
  secret_scan_result are types.SimpleNamespace instances (not dicts,
  not dataclasses) with every real field set
When write_provenance runs
Then it writes a manifest without raising, and license_scan/secret_scan
  in the written JSON carry every one of those fields with the same
  values
```
