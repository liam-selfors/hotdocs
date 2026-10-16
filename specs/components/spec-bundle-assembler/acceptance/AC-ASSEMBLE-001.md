# AC-ASSEMBLE-001

Covers: R-ASSEMBLE-001
Kind: compiled

```gherkin
Given a component with spec.md, interface.md, constraints.md, and
  acceptance.md
When assemble runs in cold mode for that component
Then the resulting SpecBundle contains spec, interface, and constraints, and
  contains no field derived from acceptance.md
```
