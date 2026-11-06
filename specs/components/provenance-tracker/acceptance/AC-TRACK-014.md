# AC-TRACK-014

Covers: R-TRACK-009
Kind: generated-test

The module's `check_readiness` and `last_requirement_failures` are
replaced by recording fakes (`interface/cli.md`).

```gherkin
Given check_readiness returning ready false with not_ready_reasons
  ["comp-a: provenance miss"]
When main(["verify", "--changed", "comp-a", "--changed=comp-b",
  "--model=m", "--seed", "3", "--repo-root=<repo_root>"]) runs
Then it returns 1, prints "not ready" and "comp-a: provenance miss",
  and check_readiness received changed_ids ["comp-a", "comp-b"],
  model "m", and seed 3

Given check_readiness returning ready true
When main(["verify", "--format=json", "--repo-root", "<repo_root>"]) runs
Then it returns 0, prints JSON whose ready is true, and check_readiness
  received no changed_ids

Given last_requirement_failures returning ["R-A-001", "R-A-002"], then []
When main(["track", "feedback", "comp-a"]) runs each time
Then both return 0, printing "R-A-001,R-A-002" and then nothing

Given ["verify", "--seed=x"], ["verify", "--format=bogus"], ["verify",
  "--bogus"], ["verify", "--model"], ["track", "feedback"], or ["build"]
When main runs
Then it returns 2 and neither fake was called
```
