# AC-PACKET-015

Covers: R-PACKET-014
Kind: generated-test

```gherkin
Given testing.md's repo whose provenance-tracker stand-in reports
  components comp-foo and comp-bar, both passing, and the files
  <repo_root>/.hotdocs/screenshots/foo/test_ac_foo_002/final-1.png and
  <repo_root>/.hotdocs/screenshots/foo/test_ac_foo_001/final-1.png
  (any bytes), and nothing under .hotdocs/screenshots/bar/
When build_review_packet(["R-FOO-001"], repo_root) runs and its markdown
  rendering is made
Then the packet's screenshots is exactly {"comp-foo":
  [".hotdocs/screenshots/foo/test_ac_foo_001/final-1.png",
  ".hotdocs/screenshots/foo/test_ac_foo_002/final-1.png"],
  "comp-bar": []}, in the order of regenerated_components
And the markdown's "## Screenshots" section comes directly after
  "## Verification Results" and holds exactly the lines
  "- comp-foo: ![test_ac_foo_001/final-1.png](.hotdocs/screenshots/foo/test_ac_foo_001/final-1.png)"
  and "- comp-foo: ![test_ac_foo_002/final-1.png](.hotdocs/screenshots/foo/test_ac_foo_002/final-1.png)",
  then the line "Screenshots are local files under .hotdocs/ (not committed); attach them to the PR to show them there."

Given the same repo with no .hotdocs/screenshots/ directory at all
When the markdown rendering is made
Then its "## Screenshots" section holds "_No screenshots._" and that
  same closing line
```
