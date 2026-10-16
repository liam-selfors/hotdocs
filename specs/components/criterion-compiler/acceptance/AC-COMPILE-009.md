# AC-COMPILE-009

Covers: R-COMPILE-009
Kind: generated-test

```gherkin
Given a component's unchanged acceptance/ and interface/ content, already
  compiled once
When compile-criteria runs again against the same --out directory
Then no output file's mtime or content changes
```
