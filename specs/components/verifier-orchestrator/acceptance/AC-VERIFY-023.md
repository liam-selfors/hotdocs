# AC-VERIFY-023

Covers: R-VERIFY-019
Kind: generated-test

```gherkin
Given a fixture component whose one generated-test criterion has a
  cached test whose first line is "# hotdocs-criterion: sha256:" then 64
  zeros, a test_author stand-in recording each call and returning a
  passing test with the correct header, and a test-probe stand-in
  returning ok True
When verify(component_id, repo_root, test_author=stand_in) runs
Then test_author was called exactly once and the criterion's result is
  "pass"

Given the same fixture with a cached test carrying the correct header,
  a test-probe stand-in that returns ok False with one finding of kind
  "undefined_name" for every source, and a test_author stand-in that
  returns a test file
When verify runs
Then test_author was called exactly once, and the criterion's result is
  "fail" with failure_origin "test" and failure_detail.message
  "test failed its probe: undefined_name"

Given the same fixture with no test_author and no cached test
When verify runs
Then the criterion's result is "fail" with failure_origin "test"

Given a cached test that passes its probe and fails against the code
When verify runs with no test_author
Then the criterion's result is "fail" with failure_origin
  "implementation"
```
