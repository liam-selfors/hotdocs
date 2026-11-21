# AC-PROV-024

Covers: R-PROV-022
Kind: generated-test

```gherkin
Given a verification_report whose assets is [{"kind": "fake", "path":
  "static/a.fake", "definition_sha256": "sha256:d1", "adapter_sha256":
  "sha256:a1", "versions": {"fakec": "2.0.0"}, "lockfile_sha256": null}]
When write_provenance runs
Then both written manifests' assets equal exactly that list

Given a verification_report with no assets key, and separately a
  verification_report of null with generation_result.files empty
When write_provenance runs
Then the written manifest's assets is []
```
