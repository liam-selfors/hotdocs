# AC-AUTHOR-029

Covers: R-AUTHOR-020
Kind: generated-test

```gherkin
Given a bundle whose dependency_interfaces documents
  "build_graph(manifest, *, plan=None, dbt_links=None) -> dict" for
  comp-erd-graph, and a mock model whose response defines a top-level
  zero-argument helper build_graph() that it calls itself and installs
  nowhere
When author_test is called
Then the result has no model_call_error and its file is written

Given the same bundle and a mock model whose response holds the string
  literal "def build_graph():\n    return {}\n", written as a fake
  module's source
When author_test is called
Then the result has model_call_error with category
  "fake_signature_mismatch" naming build_graph
```
