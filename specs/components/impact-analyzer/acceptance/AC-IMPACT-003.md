# AC-IMPACT-003

Covers: R-IMPACT-003
Kind: compiled

```gherkin
Given comp-foo's interface/library.md changed relative to the prior
  commit (not interface/guarantees/), and comp-bar depends_on comp-foo
When hotdocs impact --changed comp-foo runs
Then the report's impacted list contains comp-bar with reason
  "transitive-interface" and via "comp-foo"
```
