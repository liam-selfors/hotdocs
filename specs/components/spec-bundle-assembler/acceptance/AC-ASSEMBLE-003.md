# AC-ASSEMBLE-003

Covers: R-ASSEMBLE-003
Kind: compiled

```gherkin
Given a component with uses_var: [VAR-FOO-URL]
When assemble runs for that component
Then the resulting SpecBundle's vars field contains VAR-FOO-URL's full
  declaration content
```
