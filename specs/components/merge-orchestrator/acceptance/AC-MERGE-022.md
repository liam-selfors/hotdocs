# AC-MERGE-022

Covers: R-MERGE-020
Kind: compiled

```gherkin
Given the blast radius is {comp-foo, comp-bar}, and only P-ZERO-EDIT's
  realizes-set includes comp-foo
When R-MERGE-014 determines which capabilities to run golden scenarios for
Then only P-ZERO-EDIT runs — via one query against edges, not a bespoke
  intersection
```
