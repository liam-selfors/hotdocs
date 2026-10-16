# AC-COMPILE-007

Covers: R-COMPILE-007
Kind: generated-test

```gherkin
Given a step whose literal argument contains text resembling executable code
  (e.g. a shell command or an eval-able expression) inside a quoted string
  literal
When compile-criteria runs
Then the literal is emitted as inert data in the test output, never executed
  during compilation and never emitted as executable glue code
```
