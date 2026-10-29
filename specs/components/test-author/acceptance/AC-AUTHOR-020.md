# AC-AUTHOR-020

Covers: R-AUTHOR-020
Kind: generated-test

```gherkin
Given a mock model whose response is not valid Python at all
When author_test is called
Then the result has model_call_error with category "malformed_code",
  a null file, and nothing is written to cache or to
  verification/<component>/generated-test/

Given a bundle whose dependency_interfaces documents
  "do_thing(a: int, b: str, c: dict[str, str]) -> bool" for comp-bar,
  and a mock model whose response defines a 2-argument fake aliased to
  do_thing
When author_test is called
Then the result has model_call_error with category
  "fake_signature_mismatch" naming do_thing, and nothing is written to
  cache or to verification/<component>/generated-test/

Given the same dependency_interfaces and a mock model whose response
  defines a 3-argument fake aliased to do_thing
When author_test is called
Then the result succeeds normally with no model_call_error
```
