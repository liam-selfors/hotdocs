# AC-AUTHOR-020

Covers: R-AUTHOR-020
Kind: generated-test

```gherkin
Given a test-probe stand-in that records each call's test_source and
  module_name and returns ok False with one error finding, and a mock
  model replying with a valid marked test file to every prompt
When author_test(bundle for comp-widget-maker, "mock", repo_root=<tmp>,
  llm_backend=<mock>) is called
Then the stand-in was called with module_name "widget_maker" and the
  first reply's file content as test_source, and nothing is written to
  verification/widget-maker/generated-test/
```
