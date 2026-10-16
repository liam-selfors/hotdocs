# AC-ASSEMBLE-002

Covers: R-ASSEMBLE-002
Kind: compiled

```gherkin
Given a component that depends_on another component with its own spec.md,
  interface.md, and constraints.md
When assemble runs for the dependent component
Then dependency_interfaces contains only the dependency's interface.md
  content, and contains neither its spec.md nor its constraints.md
```
