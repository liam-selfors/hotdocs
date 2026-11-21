# AC-TRACK-008

Covers: R-TRACK-008
Kind: generated-test

```gherkin
Given comp-foo's most recent AttemptRecord with a non-null
  verification whose requirement_results is
  {"R-FOO-001": "pass", "R-FOO-002": "fail"}
When last_requirement_failures("comp-foo", repo_root) is called
Then it returns exactly ["R-FOO-002"]

Given comp-foo's most recent AttemptRecord whose requirement_results is
  {"R-FOO-001": "fail", "R-FOO-002": "fail"} and whose criteria are
  AC-FOO-001 covering R-FOO-001, "fail", failure_origin "test", and
  AC-FOO-002 covering R-FOO-002, "fail", failure_origin "implementation"
When last_requirement_failures("comp-foo", repo_root) is called
Then it returns exactly ["R-FOO-002"]

Given both fail, R-FOO-001 covered by a "pass" and an "environment"
  failure, R-FOO-002 by a "test" failure and one with no failure_origin
Then it returns exactly ["R-FOO-002"]
```
