# AC-PROVCHECK-013

Covers: R-PROVCHECK-008
Kind: generated-test

Fixture and valid manifest as in AC-PROVCHECK-012 (a valid, current manifest
passes). Each scenario changes exactly one thing in an otherwise valid and
current manifest, written as JSON, and calls check_sealed_provenance.

```gherkin
Given the manifest document is not an object: a JSON list, the number 5,
  a string, or null
Then reason is "manifest_invalid"

Given one top-level field is changed to a value below
Then reason is "manifest_invalid" for every one of them:
  kind "sealed", kind 5;
  version 2, version "1", version 1.0;
  component_id 5, "Comp-foo", "foo";
  owners "pipeline-team", [], [5], ["pipeline-team", ""], ["Pipeline"];
  source_path 5, "../x/", "gen/foo/", "/abs/", "a b/";
  source_hash 5, "sha256:" plus 63 hex digits, "sha256:" plus 64
    uppercase hex digits, "sha1:" plus 64 hex digits;
  verifier_version 5, "verifier-orchestrator@2", "other@2.0.0";
  written_at 5, "2026-11-02", "2026-11-02 00:00:00Z",
    "2026-11-02T00:00:00"

Given characterization is changed to one of: a list; an object missing
  criteria_total; an object with an extra key; overall "ok"; overall 5;
  criteria_passed "2"; criteria_passed true; criteria_total -1;
  criteria_passed 3 with criteria_total 2; overall "pass" with
  criteria_passed 0 and criteria_total 0
Then reason is "manifest_invalid" for every one of them

Given characterization {"overall": "fail", "criteria_passed": 0,
  "criteria_total": 2}, and separately {"overall": "fail",
  "criteria_passed": 0, "criteria_total": 0}, each otherwise valid and
  current
Then the manifest is valid: reason is "characterization_failed"

Given a component that is not sealed
When check_sealed_provenance is called
Then reason is "not_sealed" and sealed is false; for every other reason,
  and for a hit, sealed is true
```
