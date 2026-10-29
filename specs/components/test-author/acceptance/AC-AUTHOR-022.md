# AC-AUTHOR-022

Covers: R-AUTHOR-022
Kind: generated-test

```gherkin
Given any bundle
When author_test builds its prompt
Then the prompt instructs never to assert a fake was used via
  sys.modules under a guessed key, and instead to have the fake
  record its own invocation and assert against that record
```
