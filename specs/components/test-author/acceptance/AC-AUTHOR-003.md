# AC-AUTHOR-003

Covers: R-AUTHOR-003
Kind: generated-test

```gherkin
Given a second model is configured and generator used model A for this
  component's current code
When author_test runs
Then it is called with a model other than A; and when no second model is
  configured, it is called with the canonical model alone
```
