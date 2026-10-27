# AC-ASSEMBLE-005

Covers: R-ASSEMBLE-005
Kind: generated-test

```gherkin
Given a corpus with a hard-fail-severity spec-linter finding anywhere in it
When assemble runs for any component
Then assembly fails with a precondition-failure result, not a partial bundle
```
