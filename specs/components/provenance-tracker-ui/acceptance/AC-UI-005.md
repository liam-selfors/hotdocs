# AC-UI-005

Covers: R-UI-005
Kind: generated-test

```gherkin
Given a component with no AttemptRecord at all under .hotdocs/attempts/
When the page renders its node
Then it renders a clear "not yet attempted" state, visually distinct
  from passing and failing, not an error and not a blank node
```
