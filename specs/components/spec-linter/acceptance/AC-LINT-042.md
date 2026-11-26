# AC-LINT-042

Covers: R-LINT-036
Kind: generated-test

```gherkin
Given an otherwise lint-clean corpus whose component comp-foo's
  frontmatter has, separately, "drivers: [Bad_Name]", "drivers: [nodrv]",
  and "drivers: [mine]" with
  specs/architecture/test-driver-mine.md present and depends_on []
When lint runs
Then there is exactly one fail finding on that drivers: line, with the
  message "driver 'Bad_Name' is not a driver name", "test driver 'nodrv'
  has no definition or adapter", or "test driver 'mine' is defined in
  this repository; depends_on must list comp-driver-mine"

Given "drivers: [browser]" with the tool's own driver-browser adapter
When lint runs
Then there is no finding on that line
```
