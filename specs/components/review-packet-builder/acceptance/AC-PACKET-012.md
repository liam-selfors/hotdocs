# AC-PACKET-012

Covers: R-PACKET-012
Kind: generated-test

```gherkin
Given argv ["review-packet", "build", "--changed=R-FOO-001",
  "--repo-root=<a real repo with a provenance-tracker fake
  installed>", "--format=json"]
When main(argv) runs
Then it returns 0 and prints a JSON packet whose verification_results
  and residual_risk fields are rendered with real content, and whose
  exemption_changes.sealed/pinned_overrides fields are present (empty
  is correct here -- this fixture's own git history has no sealed or
  override change to detect)

Given the first scenario's repo
When main(["review-packet", "build", "--changed", "R-FOO-001",
  "--changed", "comp-foo", "--repo-root", "<that repo>", "--format",
  "json"]) runs
Then it returns 0 and the printed JSON's changed_requirements is
  ["R-FOO-001"]

Given argv ["review-packet", "build", "--repo-root=<a real repo>"]
  with no --changed at all, or ["review-packet", "serve",
  "--changed=R-FOO-001"], or ["review-packet"], or one ending in a bare
  "--changed", "--repo-root" or "--format"
When main(argv) runs
Then it returns 2

Given argv ["review-packet", "build", "--changed=R-FOO-001",
  "--repo-root=<a real repo>", "--format=bogus"]
When main(argv) runs
Then it returns 2

Given argv ["review-packet", "build", "--changed=R-FOO-001",
  "--repo-root=<a repo whose provenance-tracker raises UsageError>"]
When main(argv) runs
Then it returns 1

Given the first scenario's repo, whose one verification result is
  {"z": 1, "a": 2}
When main runs once with --format=json and once with no --format
Then in each printed output the text "a" appears before "z" within
  that result
```
