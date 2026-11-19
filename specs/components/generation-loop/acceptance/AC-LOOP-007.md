# AC-LOOP-007

Covers: R-LOOP-007
Kind: generated-test

```gherkin
Given a repo_root whose verification/widget/generated-test/test_ac_w_1.py
  holds "x = 1", a generate stand-in returning files, a passing
  check_surface, and a verify stand-in always returning overall "fail"
  with one criterion {"id": "AC-W-1", "kind": "generated-test",
  "result": "fail", "failure_origin": "implementation", "covers": "R-W-1"}
When run_attempts for comp-widget runs with max_attempts=3
Then the attempts' reauthored_tests are [], ["AC-W-1"] and [] in order,
  and the test file no longer exists

Given the verify stand-in instead rewrites that file with different
  content on every call
When run_attempts runs with max_attempts=3
Then every attempt's reauthored_tests is [] and the file exists

Given the same first fixture with max_attempts=2
When run_attempts runs
Then both attempts' reauthored_tests are [] and the file still exists
```
