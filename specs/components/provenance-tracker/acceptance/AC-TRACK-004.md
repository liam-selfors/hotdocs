# AC-TRACK-004

Covers: R-TRACK-004
Kind: generated-test

```gherkin
Given a plain dict with the GenerationResult fields as
  generation_result, a plain dict with the VerificationReport fields as
  verification_report, and spec_bundle_hash "sha256:abc"
When write_attempt_record("comp-foo", generation_result,
  verification_report, "sha256:abc", repo_root) runs
Then it returns an AttemptRecord whose generation and verification
  values come from those two dicts, one file exists under
  .hotdocs/attempts/comp-foo/, and the source of the provenance_tracker
  module, read with inspect.getsource, contains neither
  "component_gate_runner" nor "ComponentPipelineResult"
```
