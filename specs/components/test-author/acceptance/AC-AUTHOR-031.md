# AC-AUTHOR-031

Covers: R-AUTHOR-031
Kind: generated-test

```gherkin
Given a bundle whose testing is "Write fixtures with write_fixture(repo_root).", a
  test-probe stand-in returning ok true, and a mock model that records
  each prompt and replies with a valid marked test file
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the first recorded prompt contains the line "## Test spec" and
  contains "Write fixtures with write_fixture(repo_root)."

Given the same call with testing ""
When author_test is called
Then the first recorded prompt does not contain "## Test spec"
```
