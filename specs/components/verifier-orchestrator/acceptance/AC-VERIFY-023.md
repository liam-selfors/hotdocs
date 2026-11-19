# AC-VERIFY-023

Covers: R-VERIFY-019
Kind: generated-test

```gherkin
Given a fixture component whose one generated-test criterion's cached
  test has no header line, or "# hotdocs-criterion: sha256:" then 64
  zeros, a test_author stand-in recording its calls and returning a
  passing test with the correct header, and a test-probe stand-in
  returning ok True
When verify(component_id, repo_root, test_author=stand_in) runs
Then test_author was called exactly once and the criterion's result is
  "pass"

Given a cached passing test with the correct header
When verify runs
Then test_author was never called and the criterion's result is "pass"

Given a cached test with the correct header, a test-probe stand-in
  returning ok False with one finding of kind "undefined_name", and a
  test_author stand-in returning a test file
When verify runs
Then test_author was called exactly once, and the criterion's result is
  "fail" with failure_origin "test" and failure_detail.message
  "test failed its probe: undefined_name"

Given a cached current test that passes its probe and fails against
  the code
When verify runs with no test_author
Then the criterion's result is "fail" with failure_origin
  "implementation"
```
