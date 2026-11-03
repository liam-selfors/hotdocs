# AC-PROV-018

Covers: R-PROV-018
Kind: generated-test

```gherkin
Given a repo_root and SealedProvenanceInputs for "comp-foo" with owners
  ["pipeline-team", "alice"], source_path "pipeline/foo/", source_hash
  "sha256:" followed by 64 hex digits, verifier_version
  "verifier-orchestrator@2.0.0", and a verification_report whose
  overall is "pass" and whose criteria are three entries with result
  "pass"
When write_sealed_provenance("comp-foo", inputs, repo_root) runs
Then <repo_root>/pipeline/foo/.sealed-provenance.json exists and parses
  as JSON with exactly the keys kind, version, component_id, owners,
  source_path, source_hash, verifier_version, characterization, and
  written_at, in that order; kind is "sealed-provenance", version is 1,
  characterization is {"overall": "pass", "criteria_passed": 3,
  "criteria_total": 3}, and the other inputs are copied unchanged
And nothing was written under <repo_root>/gen/ or <repo_root>/verification/

Given the same inputs but one criteria entry has result "fail" and the
  report's overall is "fail"
When write_sealed_provenance runs
Then characterization is {"overall": "fail", "criteria_passed": 2,
  "criteria_total": 3}

Given inputs passed as a plain dict, and a report whose criteria
  entries are objects exposing result as an attribute
When write_sealed_provenance runs
Then the same manifest is written
```
