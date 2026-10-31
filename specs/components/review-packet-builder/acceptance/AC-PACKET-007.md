# AC-PACKET-007

Covers: R-PACKET-007
Kind: generated-test

```gherkin
Given a component committed without sealed: true, then a second real
  commit changing its component.md to sealed: true
When build_review_packet runs
Then exemption_changes.sealed includes that component

Given that same sealed-only PR (no .overrides.json change at all), fed
  through main(["review-packet", "build", ...]) with no --format
When the markdown rendering is inspected
Then its Exemption Changes section lists the sealed component under
  Sealed and renders Pinned Overrides as empty -- never both lists
  rendered identically regardless of which one actually changed
```
