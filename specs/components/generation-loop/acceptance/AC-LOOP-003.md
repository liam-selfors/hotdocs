# AC-LOOP-003

Covers: R-LOOP-003
Kind: generated-test

```gherkin
Given a generate stand-in returning files and recording its feedback
  argument, a passing check_surface, and a verify stand-in returning,
  in call order, overall "fail" with criteria [{"covers": "R-W-3",
  "result": "fail", "failure_origin": "implementation"}, {"covers":
  "R-W-1", "result": "fail", "failure_origin": "test"}, {"covers":
  "R-W-2", "result": "pass"}], then overall "fail" with criteria
  [{"covers": "R-W-2", "result": "fail", "failure_origin":
  "implementation", "failure_detail": {"message": "secret detail"}}],
  then overall "pass"
When run_attempts(..., retry_feedback=["R-W-9", "R-W-9"]) is called
Then the feedback arguments generate received are ["R-W-9"],
  ["R-W-3", "R-W-9"] and ["R-W-2", "R-W-3", "R-W-9"]; the attempts'
  failed_requirements are ["R-W-3"], ["R-W-2"] and []; and "secret
  detail" appears in no recorded generate argument
```
