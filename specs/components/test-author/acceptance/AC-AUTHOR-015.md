# AC-AUTHOR-015

Covers: R-AUTHOR-015
Kind: generated-test

```gherkin
Given any bundle
When author_test builds its prompt
Then the prompt states that a test depending on a spec-linter-checked
  precondition should self-check the constructed fixture against
  spec-linter's own lint() first, asserting zero hard-fail findings,
  before exercising the behavior actually under test
```
