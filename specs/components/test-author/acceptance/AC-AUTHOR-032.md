# AC-AUTHOR-032

Covers: R-AUTHOR-020
Kind: generated-test

```gherkin
Given a bundle whose testing ends with "\n## Test driver: browser\n\nUse
  the browser fixture.", a test-probe stand-in that records each call's
  keyword arguments and returns ok true, and a mock model replying with
  a valid marked test file
When author_test(bundle, "mock", repo_root=<tmp>, llm_backend=<mock>)
  is called
Then the stand-in's one recorded call has drivers ["browser"]

Given the same call with testing ""
When author_test is called
Then the recorded call has drivers []
```
