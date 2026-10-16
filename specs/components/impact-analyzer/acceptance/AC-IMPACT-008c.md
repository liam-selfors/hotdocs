# AC-IMPACT-008c

Covers: R-IMPACT-008
Kind: compiled

```gherkin
Given comp-foo has two guarantees, G-FOO-001 and G-FOO-002; comp-bar
  depends_on comp-foo and declares depends_on_guarantees: [G-FOO-001] only;
  and this commit changes G-FOO-001
When hotdocs impact --changed comp-foo runs
Then the report's impacted list contains comp-bar with reason
  "transitive-guarantee" naming G-FOO-001 — narrowing excludes irrelevant
  changes, it does not exclude comp-bar from relevant ones
```
