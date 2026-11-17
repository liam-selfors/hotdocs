# AC-GEN-008

Covers: R-GEN-008
Kind: generated-test

```gherkin
Given a mock model that raises a network error
When generate is called
Then model_call_error is non-null, files is empty, and cache_hit is false

Given a mock model whose text is "I cannot: the bundle omits X." with
  no file blocks
When generate is called
Then model_call_error has category "empty_response" and message
  "the model reply contained no files; it began:\nI cannot: the bundle omits X.",
  files is empty, and nothing is written or cached

Given a mock model whose text is 4010 characters "a", with no file
  blocks
When generate is called
Then model_call_error's message ends with "\n[10 more characters]"

Given a mock model whose text is "  \n"
When generate is called
Then model_call_error is {"category": "empty_response", "message":
  "the model reply was empty"}
```
