# AC-SIZE-006

Covers: R-SIZE-001
Kind: generated-test

```gherkin
Given a component comp-hub with six files under interface/guarantees/,
  26 acceptance criteria, and eleven other components whose depends_on
  each name comp-hub
When check(repo_root) runs
Then comp-hub gets warn R-SIZE-001 findings whose messages name
  guarantee_count with 6, acceptance_count with 26 and fan_in with 11,
  and none of the other components gets an R-SIZE-001 finding naming
  fan_in or fan_out
```
