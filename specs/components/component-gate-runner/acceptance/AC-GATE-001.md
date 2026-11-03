# AC-GATE-001

Covers: R-GATE-001
Kind: generated-test

Every scenario in this component's criteria builds a repo_root with
`specs/components/foo/component.md` (id `comp-foo`) and a faked module
under `gen/<slug>/` for each dependency `interface/library.md` lists,
each appending one line per call to a shared invocation log file.
Every faked provenance-checker also defines `current_sealed_key`,
returning `None` unless a scenario says otherwise.

```gherkin
Given a faked provenance-checker whose current_provenance_key returns
  spec_bundle_hash "sha256:k" and gate_versions {"verifier": "v@1"},
  and whose check_provenance reports a hit with a passing
  verification_report and an unblocked license_scan
When run_component_gates("comp-foo", repo_root, "m") is called
Then check_provenance received "sha256:k" and {"verifier": "v@1"}, no
  other dependency was called, provenance_hit is true, blocked is
  false, and verification is the hit's verification_report

Given the same, but the hit's verification_report.overall is "fail"
When run_component_gates is called
Then generator was called exactly once and provenance_hit is false
```
