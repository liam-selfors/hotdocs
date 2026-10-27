# AC-UI-007

Covers: R-UI-007
Kind: generated-test

```gherkin
Given the page is showing a blast-radius view for changed_ids=[comp-foo]
  and a developer switches to the whole-corpus view
When the scope switch happens
Then check_readiness is called again with no changed_ids, not re-used
  or client-side-filtered from the earlier blast-radius result
```
