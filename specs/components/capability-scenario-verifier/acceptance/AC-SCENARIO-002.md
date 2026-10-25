# AC-SCENARIO-002

Covers: R-SCENARIO-002
Kind: compiled

```gherkin
Given the blast radius is {comp-foo, comp-bar}, and only P-ZERO-EDIT's
  realizes-set includes comp-foo
When the capability-intersection lookup runs
Then only P-ZERO-EDIT is selected — via one query against edges, not a
  bespoke intersection
```
