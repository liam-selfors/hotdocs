# AC-IMPACT-008b

Covers: R-IMPACT-008
Kind: generated-test

```gherkin
Given comp-foo has two guarantees, G-FOO-001 and G-FOO-002; comp-bar
  depends_on comp-foo and declares depends_on_guarantees: [G-FOO-001] only;
  and this commit changes G-FOO-002 but not G-FOO-001
When hotdocs impact --changed comp-foo runs
Then the report's impacted list does NOT contain comp-bar on this basis —
  narrowed, because comp-bar explicitly declared it only relies on
  G-FOO-001
```
