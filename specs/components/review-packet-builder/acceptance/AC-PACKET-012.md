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

Given a repo whose provenance-tracker fake reports: one license-scan
  flag, one secret-scan flag, one residual-risk finding, and one
  intersecting capability scenario, AND whose git history has a real
  sealed: true transition and a real gen/<slug>/.overrides.json
  addition
When main(["review-packet", "build", "--changed=R-FOO-001",
  "--repo-root=<that repo>"]) runs with no --format at all
Then it returns 0 and the printed markdown rendering contains, under
  their own section headings, the license flag's own detail content
  (e.g. the flagged file/package name, not merely the word "blocked"),
  the secret flag's own detail content (not merely the word "flagged"),
  the residual-risk message, the capability scenario id, the sealed
  component id, and the pinned-override component id -- never a
  generic placeholder standing in for any of them, and never a
  boolean status word standing in for the real flagged detail

Given a repo whose provenance-tracker fake reports zero license-scan
  flags, zero secret-scan flags, zero intersecting capability
  scenarios, and zero residual-risk findings, fed through
  main(["review-packet", "build", "--changed=R-FOO-001",
  "--repo-root=<that repo>"]) with no --format at all
When the markdown rendering is inspected
Then its License Scan, Secret Scan, and Capability Scenarios
  sections each render their own clean/empty placeholder -- while
  Verification Results still renders real content for the one
  regenerated component

Given argv ["review-packet", "build", "--repo-root=<a real repo>"]
  with no --changed at all
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
```
