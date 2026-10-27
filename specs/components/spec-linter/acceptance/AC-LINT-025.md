# AC-LINT-025

Covers: R-LINT-025
Kind: generated-test

```gherkin
Given a component whose Purpose section is 160 words long, with no
  decision citation anywhere in it
When the linter runs
Then it fails with R-LINT-025 naming the hard-fail threshold —
  confirming this rule fires independently of R-LINT-024, on length
  alone
```
