# AC-ASSEMBLE-008

Covers: R-ASSEMBLE-008
Kind: generated-test

```gherkin
Given a component with existing gen/<component>/ content
When assemble runs in hint mode for that component
Then hint_code contains that content, keyed by relative path, every
  other field except spec_bundle_hash and spec_bundle_parts matches what
  cold mode produces, and spec_bundle_hash and spec_bundle_parts' spec
  differ from cold mode's, since R-ASSEMBLE-007 hashes the mode and
  gen/<component>/ in hint mode
```
