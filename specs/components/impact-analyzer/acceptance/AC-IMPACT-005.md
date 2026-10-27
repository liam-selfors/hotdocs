# AC-IMPACT-005

Covers: R-IMPACT-005
Kind: generated-test

```gherkin
Given P-ZERO-EDIT's capability scenarios changed, and comp-foo has
  realizes: [P-ZERO-EDIT]
When hotdocs impact --changed P-ZERO-EDIT runs
Then the report's impacted list contains comp-foo with reason
  "transitive-capability" and via "P-ZERO-EDIT"
```
