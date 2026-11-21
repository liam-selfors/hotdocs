# AC-AUTHOR-016

Covers: R-AUTHOR-012
Kind: generated-test

```gherkin
Given a bundle for comp-widget-maker whose dependency_interfaces is {},
  a test-probe stand-in returning ok true, and a mock model that records
  each prompt and replies with a valid marked test file
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the first recorded prompt contains the line
  "- Every `requirements/` file of every fixture component has a matching `acceptance/` file with a `Covers:` tag."
```
