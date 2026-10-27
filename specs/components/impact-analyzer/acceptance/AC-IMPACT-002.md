# AC-IMPACT-002

Covers: R-IMPACT-002
Kind: generated-test

```gherkin
Given comp-foo's component.md changed but every file under its interface/
  is byte-identical to the prior commit, and comp-bar depends_on comp-foo
When hotdocs impact --changed comp-foo runs
Then the report's impacted list contains comp-foo with reason "direct" and
  does NOT contain comp-bar
```
