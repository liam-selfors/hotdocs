# AC-SIZE-001

Covers: R-SIZE-001
Kind: generated-test

```gherkin
Given a component whose generated-code LOC estimate exceeds 1500
When check(repo_root) runs on it
Then the report contains a fail-severity finding for rule R-SIZE-001 whose
  message names the dimension `generated_code_loc`
```
