# AC-LOOP-004

Covers: R-LOOP-004
Kind: generated-test

```gherkin
Given a generate stand-in returning files, a passing check_surface, and
  a verify stand-in always returning overall "fail" with no criteria
When run_attempts(..., max_attempts=2) is called
Then generate was called twice, passed is False, stop_reason is
  "max_attempts", and commit_cache was never called

Given the verify stand-in returns overall "fail" then "pass"
When run_attempts(..., max_attempts=3) is called in single mode
Then generate was called twice, passed is True, stop_reason is "passed",
  and commit_cache was called once with the second generation result

Given the same stand-ins
When run_attempts(..., mode="agentic") is called
Then generate_agentic was called twice, generate never, and commit_cache
  never
```
