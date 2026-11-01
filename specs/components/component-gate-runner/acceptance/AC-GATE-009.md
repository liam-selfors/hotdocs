# AC-GATE-009

Covers: R-GATE-009
Kind: generated-test

```gherkin
Given the faked dependencies, a provenance miss, one generated file,
  and verify returning overall "pass"
When main(["generate", "comp-foo", "--model=m", "--seed=2",
  "--retry-feedback=R-FOO-001,R-FOO-002", "--repo-root=<repo_root>",
  "--format=json"]) runs
Then it returns 0, prints JSON whose blocked is false, and generate
  received model "m" and ["R-FOO-001", "R-FOO-002"]

Given the same
When main(["generate", "comp-foo", "--model", "m", "--repo-root",
  "<repo_root>", "--format", "text"]) runs
Then it returns 0 and prints text containing "comp-foo" and "passed"

Given a faked generator returning a model_call_error
When main runs generate for comp-foo with --model=m
Then it returns 1

Given no --model, or the component id "comp-nope" with no spec
  directory, or --seed=x, or --format=bogus, or an unknown argument,
  or ["build", "comp-foo", "--model=m"], or "--model" as the last
  argument with no value
When main runs
Then it returns 2 and no faked dependency was called
```
