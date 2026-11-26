# AC-PROV-024

Covers: R-PROV-022
Kind: generated-test

```gherkin
Given a verification_report whose assets is [{"kind": "fake", "path":
  "static/a.fake", "definition_sha256": "sha256:d1", "adapter_sha256":
  "sha256:a1", "versions": {"fakec": "2.0.0"}, "lockfile_sha256": null}]
and whose drivers is [{"name": "fake", "definition_sha256": null,
  "adapter_sha256": "sha256:a2", "versions": {"fakedrv": "2.0"},
  "lockfile_sha256": null}]
When write_provenance runs
Then both written manifests' assets and drivers equal exactly those lists

Given a verification_report with no assets or drivers key, and separately a
  verification_report of null with generation_result.files empty
When write_provenance runs
Then the written manifest's assets and drivers are []
```
