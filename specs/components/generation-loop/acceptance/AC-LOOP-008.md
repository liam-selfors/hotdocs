# AC-LOOP-008

Covers: R-LOOP-001
Kind: generated-test

```gherkin
Given stand-ins whose generate returns, in call order, results with
  model_call_error categories "missing_asset", then "malformed_layout",
  then files {"widget.py": "X = 1"}, a passing check_surface, and a
  verify stand-in returning overall "pass"
When run_attempts("comp-widget", bundle, repo_root, "m",
  max_attempts=3) is called
Then generate was called three times, the attempts' outcomes are
  "generation_failed", "generation_failed" and "passed" with
  error_category "missing_asset", "malformed_layout" and None, passed
  is True and stop_reason is "passed"
```
