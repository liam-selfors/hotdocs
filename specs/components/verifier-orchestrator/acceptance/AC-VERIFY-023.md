# AC-VERIFY-023

Covers: R-VERIFY-019
Kind: generated-test

```gherkin
Given a fixture component whose one generated-test criterion has a
  cached test whose first line is "# hotdocs-criterion: sha256:" then 64
  zeros, and a test_author stand-in recording each call and returning a
  passing test with the correct header
When verify(component_id, repo_root, test_author=stand_in) runs
Then test_author was called exactly once and the criterion's result is
  "pass"

Given the same fixture whose cached test has no header line
When verify(component_id, repo_root, test_author=stand_in) runs
Then test_author was called exactly once and the criterion's result is
  "pass"

Given the same fixture with a cached passing test carrying the correct
  header
When verify(component_id, repo_root, test_author=stand_in) runs
Then test_author was never called and the criterion's result is "pass"

Given a cached test carrying the correct header that fails against the
  code
When verify runs with no test_author
Then the criterion's result is "fail" with failure_origin
  "implementation"
```
