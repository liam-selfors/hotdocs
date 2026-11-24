# AC-AUTHOR-009

Covers: R-AUTHOR-009
Kind: generated-test

```gherkin
Given a mock model whose response wraps the real test code in a
  markdown code fence and a line of narration before and after the
  nonce-delimited BEGIN/END markers
When author_test is called
Then the resulting TestAuthoringResult's file content is exactly the
  text between the markers, with no fence, narration, or marker text
  itself included

Given a mock model whose response contains no BEGIN/END marker pair at
  all (model_call_error is null, but the text does not conform)
When author_test is called
Then the resulting TestAuthoringResult has a null file and is treated
  as a distinct authoring failure, and nothing is written to
  verification/<component>/generated-test/
```
