# AC-COMPILE-006

Covers: R-COMPILE-006
Kind: generated-test

```gherkin
Given a successful compile of a component named "widget"
When the output files are written
Then they are written under verification/widget/compiled/ and nowhere under
  specs/
```
