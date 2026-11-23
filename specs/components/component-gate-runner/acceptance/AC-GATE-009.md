# AC-GATE-009

Covers: R-GATE-009
Kind: generated-test

```gherkin
Given the faked dependencies, a provenance miss, and a faked
  run_attempts returning passed true with one attempt entry
  {"number": 1, "outcome": "passed"}
When main(["generate", "comp-foo", "--model=m", "--seed=2",
  "--retry-feedback=R-FOO-001,R-FOO-002", "--repo-root=<repo_root>",
  "--format=json"]) runs
Then it returns 0, prints JSON whose blocked is false, and run_attempts
  received model "m", seed 2 and ["R-FOO-001", "R-FOO-002"]

Given the same
When main(["generate", "comp-foo", "--model", "m", "--repo-root",
  "<repo_root>", "--format", "text"]) runs
Then it returns 0 and prints text containing "comp-foo", "passed" and
  "attempt 1: passed"

Given a faked run_attempts whose last attempt is "generation_failed"
  with model_call_error {"category": "empty_response", "message": "no
  files"}
When main runs generate for comp-foo with --model=m
Then it returns 1 and prints text containing
  "model_call_error: empty_response: no files"

Given a faked run_attempts whose last attempt is "surface_failed", with
  one file, verification_report None and a surface_report whose one
  finding has message "static/a.js: no interface file"
When main runs generate for comp-foo with --model=m
Then it returns 0 and prints text containing "surface_check_failed" and
  "surface: static/a.js: no interface file"

Given verify returning overall "fail" with one criterion AC-FOO-001,
  result "fail", failure_origin "test", failure_detail message
  "test authoring failed: network: dropped"
When main runs generate for comp-foo with --model=m
Then it returns 1 and prints text containing "test_authoring_failed"
  and "AC-FOO-001: test authoring failed: network: dropped"

Given verify returning overall "fail" with one criterion whose
  failure_detail actual is {"b", "a"}
When main runs generate for comp-foo with --model=m --format=json
Then it returns 0 and prints JSON in which that actual is ["a", "b"]

Given verify returning overall "fail", mutation_score None and
  mutation_error "mutation baseline failed in the sandbox: pytest exited 1"
When main runs generate for comp-foo with --model=m
Then it returns 0 and prints text containing
  "mutation_error: mutation baseline failed in the sandbox: pytest exited 1"

Given a faked license scan with evaluated false and reason
  "no-reference-corpus"
When main runs generate for comp-foo with --model=m
Then it prints text containing
  "license_scan not evaluated: no-reference-corpus"

Given no --model, or the component id "comp-nope" with no spec
  directory, or --seed=x, or --format=bogus, or an unknown argument,
  or ["build", "comp-foo", "--model=m"], or "--model" as the last
  argument with no value
When main runs
Then it returns 2, its first stderr line starts "usage error: ", and no
  faked dependency was called
```
