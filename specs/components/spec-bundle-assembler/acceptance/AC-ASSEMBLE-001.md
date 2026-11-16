# AC-ASSEMBLE-001

Covers: R-ASSEMBLE-001
Kind: generated-test

```gherkin
Given a component with component.md, requirements/, interface/,
  constraints.md, and acceptance/
When assemble runs in cold mode for that component
Then the resulting SpecBundle contains spec, interface, and constraints
  content, and contains no field derived from acceptance/
```
