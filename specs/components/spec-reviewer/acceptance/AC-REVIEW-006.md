# AC-REVIEW-006

Covers: R-REVIEW-006
Kind: generated-test

```gherkin
Given a mock llm_backend replying 'ok {"conflicts": true, "rationale":
  "narrower"}' and counting its calls
When judge = glossary_judge("mock", backend) and judge("Foo", "local
  meaning", "glossary meaning") is called
Then it returns (True, "narrower"), the backend was called once, and
  its prompt held "Foo", "local meaning" and "glossary meaning"

Given mock backends replying "no json", replying '{"conflicts": "yes",
  "rationale": "r"}', and returning a model_call_error of "timeout"
When the judge built from each is called
Then each call returns None
```
