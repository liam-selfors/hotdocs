# AC-IMPACT-013

Covers: R-IMPACT-008
Kind: generated-test

```gherkin
Given a lint-clean git fixture where comp-foo's interface/guarantees/
  holds G-FOO-001.md, G-FOO-002.md, G-FOO-003.md, README.md, notes.txt
  and old/G-FOO-009.md; comp-qux has G-QUX-001; and comp-bar has
  depends_on: [comp-foo, comp-qux] and depends_on_guarantees: [G-QUX-001]
And on the feature branch only README.md, notes.txt and
  old/G-FOO-009.md changed
When compute_blast_radius(["comp-foo"], <repo>) runs
Then impacted is exactly [comp-foo "direct"]

Given that state after G-FOO-002.md is also edited and G-FOO-003.md
  deleted
When compute_blast_radius(["comp-foo"], <repo>) runs
Then impacted is exactly [comp-foo "direct", comp-bar
  "transitive-guarantee" via "comp-foo" with guarantee_ids
  ["G-FOO-002", "G-FOO-003"]] — comp-bar's G-QUX-001 declaration narrows
  only comp-qux's guarantees, so comp-foo's apply in full
```
