# AC-ENDPOINT-004

Covers: R-ENDPOINT-005
Kind: generated-test

```gherkin
Given a configured Anthropic credential and a backend call that fails
When the resulting ModelResponse and any logged error text are
  inspected
Then the credential value does not appear anywhere in either — only the
  model identifier actually used is present
```
