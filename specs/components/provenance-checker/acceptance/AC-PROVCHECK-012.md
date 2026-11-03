# AC-PROVCHECK-012

Covers: R-PROVCHECK-008
Kind: generated-test

Fixture as in AC-PROVCHECK-011. Each scenario writes the manifest as
JSON, taking source_hash from current_sealed_key unless it says otherwise.
A valid manifest has kind "sealed-provenance", version 1, component_id
"comp-foo", owners ["pipeline-team", "alice"], source_path
"pipeline/foo/", verifier_version "verifier-orchestrator@2.0.0",
characterization {"overall": "pass", "criteria_passed": 2,
"criteria_total": 2}, and written_at "2026-11-02T00:00:00Z".

```gherkin
Given a valid, current manifest
When check_sealed_provenance("comp-foo", repo_root) is called
Then hit is true, reason is null, sealed is true, verification_report is
  {"overall": "pass"}, owners and written_at are the manifest's,
  and license_scan and secret_scan are null

Given no manifest file
Then reason is "manifest_missing" and hit is false

Given a manifest that is not JSON, or has an extra key, or lacks a key,
  or has version true, or has source_hash "sha256:abc", or has an owner
  "Alice", or has overall "pass" with criteria_passed 1 of 2
Then reason is "manifest_invalid", hit is false, and owners and
  verification_report are null

Given a manifest whose component_id is "comp-bar", or whose source_path
  is "pipeline/other/"
Then reason is "component_mismatch"

Given a manifest valid in every way but source_hash is the hash of
  different content
Then reason is "source_changed"

Given owners in the manifest are ["pipeline-team"] only, or are in the
  other order
Then reason is "owners_changed"

Given verifier_version "verifier-orchestrator@1.0.0" in the manifest
Then reason is "verifier_changed"

Given characterization {"overall": "fail", "criteria_passed": 1,
  "criteria_total": 2}, otherwise valid and current
Then reason is "characterization_failed", hit is false, and
  verification_report, owners, source_hash, and written_at are null

Given a component that is not sealed
Then reason is "not_sealed"

Given any of the above
Then no file under repo_root was created, changed, or removed, not
  counting any __pycache__ directory (importing a faked dependency
  creates one)
```
