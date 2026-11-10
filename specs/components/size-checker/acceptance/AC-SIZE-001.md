# AC-SIZE-001

Covers: R-SIZE-001
Kind: generated-test

```gherkin
Given a component whose generated-code LOC estimate exceeds 1500
When check(repo_root) runs on it
Then the report contains a fail-severity finding for rule R-SIZE-001 citing
  the "Generated code per component" dimension
```
