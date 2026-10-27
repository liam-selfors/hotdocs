# AC-ASSEMBLE-002

Covers: R-ASSEMBLE-002
Kind: generated-test

```gherkin
Given a component that depends_on another component with its own
  component.md, requirements/, and constraints.md
When assemble runs for the dependent component
Then dependency_interfaces contains only the dependency's interface/
  content, and contains neither its component.md/requirements/ nor its
  constraints.md
```
