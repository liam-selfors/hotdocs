# AC-PACKET-007

Covers: R-PACKET-007
Kind: generated-test

```gherkin
Given specs/components/foo/component.md (component id comp-foo; the
  directory is the bare slug, as for every component here) committed
  without sealed: true, then a second real commit changing it to
  sealed: true
When build_review_packet runs
Then exemption_changes.sealed includes that component

Given that same sealed-only PR (no .overrides.json change at all), fed
  through main(["review-packet", "build", ...]) with no --format
When the markdown rendering is inspected
Then its Exemption Changes section lists the sealed component under
  Sealed and renders Pinned Overrides as empty -- never both lists
  rendered identically regardless of which one actually changed

Given one component.md first committed with sealed: true and later
  edited in another commit (still sealed: true), a second first
  committed with no sealed line and later changed to sealed: false, and
  a gen/comp-old/.overrides.json present at the PR diff-base and
  deleted in this PR
When build_review_packet runs
Then exemption_changes.sealed includes neither component and
  exemption_changes.pinned_overrides does not include comp-old
```
