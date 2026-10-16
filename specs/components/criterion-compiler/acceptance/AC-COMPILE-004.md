# AC-COMPILE-004

Covers: R-COMPILE-004
Kind: generated-test

```gherkin
Given a criterion AC-FOO-003 with Covers: R-FOO-003
When it compiles successfully
Then the emitted test file contains R-FOO-003 as traceable metadata (e.g. a
  comment or decorator), not just an opaque test name
```
