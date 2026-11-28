# AC-VERIFY-002

Covers: R-VERIFY-002
Kind: generated-test

```gherkin
Given a component with one generated-test criterion, verifier-fixtures.md's
  assembler and probe stand-ins, and a current cached test (its first line
  the correct header) at verification/<slug>/generated-test/<criterion test
  filename>, which writes a marker file under repo_root when it runs and
  passes
When verify runs with no test_author
Then the marker file exists and that criterion's result is "pass"
```
