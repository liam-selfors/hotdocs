# AC-AUTHOR-015

Covers: R-AUTHOR-015
Kind: generated-test

```gherkin
Given a bundle for comp-widget-maker whose dependency_interfaces is {},
  a test-probe stand-in returning ok true, and a mock model that records
  each prompt and replies with a valid marked test file
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the first recorded prompt contains the line
  "    import widget_maker" and the line
  "    assert spec_linter.lint(None, repo_root).hard_failures == 0",
  and contains no "@MODULE@"

Given a bundle for comp-widget-maker whose module_names is
  ["alpha_mod", "beta_mod"], a test-probe stand-in returning ok true,
  and a mock model that records each prompt and replies with a valid
  marked test file
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the first recorded prompt contains the line "    import alpha_mod"
  and does not contain the line "    import widget_maker"
```
