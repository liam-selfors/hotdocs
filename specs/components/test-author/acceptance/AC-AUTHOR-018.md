# AC-AUTHOR-018

Covers: R-AUTHOR-012
Kind: generated-test

```gherkin
Given a bundle whose criterion requires a synthetic fixture
When author_test builds its prompt
Then the prompt states that any document using status: ratified must
  also set last_ratified_commit to a present, clearly-fake placeholder
  value
```
