# AC-ASSIST-003

Covers: R-ASSIST-003
Kind: generated-test

```gherkin
Given a predicted blast radius of one component
When assist runs
Then hint_previews contains a hint-mode preview for that component,
  produced without a full cold regen
```
