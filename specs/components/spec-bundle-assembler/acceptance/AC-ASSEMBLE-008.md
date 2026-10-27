# AC-ASSEMBLE-008

Covers: R-ASSEMBLE-008
Kind: generated-test

```gherkin
Given a component with existing gen/<component>/ content
When assemble runs in hint mode for that component
Then hint_code contains that content, keyed by relative path, and every
  other field matches what cold mode would have produced
```
