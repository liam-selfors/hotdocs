# AC-TRACK-008

Covers: R-TRACK-008
Kind: generated-test

```gherkin
Given comp-foo's most recent AttemptRecord with a non-null
  verification whose requirement_results is
  {"R-FOO-001": "pass", "R-FOO-002": "fail"}
When last_requirement_failures("comp-foo", repo_root) is called
Then it returns exactly ["R-FOO-002"]
```
