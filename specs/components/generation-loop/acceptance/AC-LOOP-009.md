# AC-LOOP-009

Covers: R-LOOP-004
Kind: generated-test

```gherkin
Given a generate stand-in returning files {"widget.py": "X = 1"}, a
  passing check_surface, and a verify stand-in always returning overall
  "fail" with criteria [{"covers": "R-W-1", "result": "fail",
  "failure_origin": "environment", "failure_detail": {"message":
  "javascript needs node >= 24"}}, {"covers": "R-W-2", "result": "fail",
  "failure_origin": "implementation"}]
When run_attempts("comp-widget", bundle, repo_root, "m",
  max_attempts=3) is called in single mode
Then generate and verify were each called once, the only attempt's
  outcome is "verification_failed" with failed_requirements ["R-W-2"],
  passed is False, stop_reason is "environment", and commit_cache was
  never called

Given a generate stand-in returning model_call_error {"category":
  "environment", "message": "javascript needs node >= 24"}
When run_attempts is called the same way
Then generate was called once, verify never, the only attempt's outcome
  is "generation_failed" and stop_reason is "environment"
```
