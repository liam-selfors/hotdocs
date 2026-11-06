# AC-TRACK-009

Covers: R-TRACK-009
Kind: generated-test

Any faked provenance-checker provides current_sealed_key (returning None,
so every component here is generated), current_provenance_key,
check_provenance, and check_sealed_provenance (`interface/library.md`).

```gherkin
Given changed_ids naming one changed component, impact-analyzer
  reporting a blast radius of two components, and provenance-checker
  reporting a hit for one and a miss for the other
When check_readiness is called with those changed_ids
Then the report's scope is blast-radius, its components map has
  exactly those two entries, and the missing one is named in
  not_ready_reasons, and component-gate-runner is never called

Given no changed_ids
When check_readiness is called
Then every component under specs/components/ is checked via
  provenance-checker, and the report's scope is whole-corpus

Given a provenance-checker hit carrying a verification_report whose
  requirement_results is {"R-FOO-001": "pass", "R-FOO-002": "fail"}
When check_readiness is called
Then that component is reported as not ready, and its
  not_ready_reasons entry contains the component id, "verification",
  and "R-FOO-002", and no call is made to component-gate-runner

Given a provenance-checker hit with a passing verification_report but
  a license_scan whose blocked is true
When check_readiness is called
Then that component's not_ready_reasons entry contains "license_scan"

Given a faked current_provenance_key returning spec_bundle_hash
  "sha256:k1" and gate_versions {"verifier": "v@1"}
When check_readiness is called
Then check_provenance received exactly "sha256:k1" and
  {"verifier": "v@1"} for every component it checked
```
