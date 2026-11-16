# AC-IMPACT-008

Covers: R-IMPACT-008
Kind: generated-test

```gherkin
Given comp-foo's interface/guarantees/G-FOO-001.md changed, and comp-bar
  depends_on comp-foo with no depends_on_guarantees declared for comp-foo
When hotdocs impact --changed comp-foo runs
Then the report's impacted list contains comp-bar with reason
  "transitive-guarantee" and via "comp-foo" — the coarse, safe default
```
