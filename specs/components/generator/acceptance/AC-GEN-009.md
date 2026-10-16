# AC-GEN-009

Covers: R-GEN-009
Kind: compiled

```gherkin
Given a component marked sealed: true with a source_path, and a second
  component with a gen/<component>/.overrides.json listing one pinned file
When generate is invoked for either component
Then generate refuses to write under that source_path, and refuses to
  overwrite the pinned file, in both cases without needing to call a model
  to know this
```
