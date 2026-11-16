# AC-CITE-004

Covers: R-CITE-004
Kind: generated-test

```gherkin
Given a decision record with supersedes: D<N> where D<N> does not exist
When check(repo_root) runs
Then that record gets an R-CITE-004 finding

Given a decision record with supersedes: D<N> where D<N> exists but is
  still status: ratified, not deprecated
When check(repo_root) runs
Then the superseding record gets an R-CITE-004 finding naming D<N>

Given a decision record with status: deprecated that no other real
  decision's supersedes field names
When check(repo_root) runs
Then that record gets an R-CITE-004 finding
```
