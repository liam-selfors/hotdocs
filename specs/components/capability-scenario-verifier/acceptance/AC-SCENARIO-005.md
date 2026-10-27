# AC-SCENARIO-005

Covers: R-SCENARIO-004
Kind: generated-test

```gherkin
Given P-ZERO-EDIT's realizing components' current gen/ content hashes
  to a value matching the committed verification/capabilities/P-ZERO-EDIT/.provenance.json
When check_capability_provenance("P-ZERO-EDIT", repo_root) is called
Then it reports a hit, and run_capability_gates does not re-run the
  scenarios

Given one realizing component's gen/ content has changed since that
  committed record was written, even though no spec_bundle_hash changed
When run_capability_gates("P-ZERO-EDIT", repo_root) is called
Then check_capability_provenance reports a miss, the scenarios are
  re-run, and a fresh record is written reflecting the new content hash
```
