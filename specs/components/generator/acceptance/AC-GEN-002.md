# AC-GEN-002

Covers: R-GEN-002
Kind: generated-test

```gherkin
Given a hint-mode SpecBundle (hint_code populated) and a mock model that
  records what it was sent
When generate is called with that bundle
Then the mock model's recorded input contains hint_code as a distinctly
  labeled section, separate from the cold bundle fields
```
