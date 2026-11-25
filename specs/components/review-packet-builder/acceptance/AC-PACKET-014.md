# AC-PACKET-014

Covers: R-PACKET-012
Kind: generated-test

```gherkin
Given a repo whose provenance-tracker fake reports: one license-scan
  flag, a top-level secret_scan flagged with one match (file a/b.py,
  line 3), one residual-risk finding, and one
  intersecting capability scenario, AND whose git history has a real
  sealed: true transition and a real gen/<slug>/.overrides.json
  addition
When main(["review-packet", "build", "--changed=R-FOO-001",
  "--repo-root=<that repo>"]) runs with no --format at all
Then it returns 0 and the printed markdown rendering contains, under
  their own section headings, the license flag's own detail content
  (e.g. the flagged file/package name, not merely the word "blocked"),
  the secret flag's own detail content ("a/b.py", not merely the word
  "flagged"),
  the residual-risk message, the capability scenario id, the sealed
  component id, the pinned-override component id, the spec diff text (a line this
  PR added to a file under specs/; the diff covers nothing else),
  "R-FOO-001", the regenerated component id, and its provenance hit
  status -- never a
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
```
