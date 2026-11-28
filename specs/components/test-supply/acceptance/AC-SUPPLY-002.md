# AC-SUPPLY-002

Covers: R-SUPPLY-002
Kind: generated-test

```gherkin
Given no committed test, and a stand-in returning model_call_error
  {"category": "network", "message": "dropped"} on its first call and a
  file with the correct header on its second
When supply is called with it
Then author.log has two lines and failure_origin is None

Given a stand-in always returning model_call_error {"category":
  "network", "message": "dropped"}, and separately one always returning
  {"category": "auth", "message": "bad key"}
When supply is called with each
Then author.log has two lines, or one, and failure_message is
  "test authoring failed: network: dropped", or
  "test authoring failed: auth: bad key", with failure_origin "test"
  and path None

Given no committed test
When supply is called with no test_author
Then failure_message is "test authoring failed: none: no test author"
```
