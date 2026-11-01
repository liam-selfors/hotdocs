# AC-PROVCHECK-010

Covers: R-PROVCHECK-006
Kind: generated-test

```gherkin
Given gen/foo/.provenance.json with spec_bundle_hash "sha256:0a1b",
  gate_versions {"license_scanner": "1"}, and a passing
  verification_report with no llm-judge criteria
When main(["check", "comp-foo", "--spec-bundle-hash=sha256:0a1b",
  "--gate-versions={\"license_scanner\": \"1\"}",
  "--repo-root=<repo_root>", "--format=json"]) runs
Then it returns 0 and prints JSON whose hit is true

Given the same repo_root
When main(["check", "comp-foo", "--spec-bundle-hash", "sha256:ffff",
  "--gate-versions", "{\"license_scanner\": \"1\"}", "--repo-root",
  "<repo_root>", "--format", "text"]) runs
Then it returns 0 and prints text containing "miss"

Given a missing --spec-bundle-hash, or --spec-bundle-hash=0a1b
  (no sha256: prefix), or --gate-versions "[1]", or
  --format=bogus, or an unknown argument, or "--repo-root" as the last
  argument with no value
When main runs
Then it returns 2
```
