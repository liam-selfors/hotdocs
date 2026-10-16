# AC-GEN-001

Covers: R-GEN-001
Kind: generated-test

```gherkin
Given a cold-mode SpecBundle and a mock model that records what it was sent
When generate is called with that bundle
Then the mock model's recorded input contains exactly the bundle's spec,
  interface, constraints, dependency_interfaces, vars, and glossary fields,
  and nothing else
```
