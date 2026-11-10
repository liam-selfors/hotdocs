# AC-CITE-005

Covers: R-CITE-005
Kind: generated-test

```gherkin
Given a decision record's builds_on naming a decision number with no
  corresponding specs/decisions/ file, and a second record's builds_on
  naming D7, one of D1-D14, never formalized as files
When check(repo_root) runs
Then only the first gets an R-CITE-005 finding
```
