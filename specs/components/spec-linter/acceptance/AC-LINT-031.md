# AC-LINT-031

Covers: R-LINT-031
Kind: generated-test

```gherkin
Given three components, each with an interface/cli.md: one with a
  requirement citing interface/cli.md and a criterion covering it, one
  whose citing requirement has no covering criterion, and one with no
  citing requirement
When the linter runs
Then only the second and third get an R-LINT-031 finding, each of
  severity warn
```
