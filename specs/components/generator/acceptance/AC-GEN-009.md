# AC-GEN-009

Covers: R-GEN-009
Kind: generated-test

```gherkin
Given a component marked sealed: true with a source_path, and a second
  component with a gen/<component>/.overrides.json listing one pinned file
When generate is invoked for either component, with a mock model that
  records whether it was ever called
Then the mock model is never called, the resulting GenerationResult has
  files empty, model_call_error null, and refused set to a reason string
  naming which exemption applied
```
