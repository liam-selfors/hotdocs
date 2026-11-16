# AC-ENDPOINT-002

Covers: R-ENDPOINT-001
Kind: generated-test

```gherkin
Given an injected mock Anthropic backend configured to return "hello"
  for any prompt
When complete() is called with that prompt and model="claude-sonnet-5"
Then the returned ModelResponse has text "hello", model "claude-sonnet-5",
  and model_call_error null
```
