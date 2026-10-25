# AC-LINT-020

Covers: R-LINT-020
Kind: compiled

```gherkin
Given comp-foo's frontmatter declares depends_on_guarantees: [G-BAR-001],
  G-BAR-001 exists under comp-bar's interface/guarantees/, and comp-foo's
  depends_on list does NOT include comp-bar
When the linter runs
Then it fails with R-LINT-018, resolved via a join against the nodes/edges
  views named in graph-query-engine.md rather than bespoke path-parsing —
  confirming owner_component_id (derived from the guarantee file's path,
  not its frontmatter, since guarantee files carry none) is what the
  check actually uses
```
