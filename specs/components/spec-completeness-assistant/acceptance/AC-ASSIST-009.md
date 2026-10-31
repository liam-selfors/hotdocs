# AC-ASSIST-009

Covers: R-ASSIST-009
Kind: generated-test

```gherkin
Given a repo_root with faked spec-linter (one "warn" finding),
  impact-analyzer (blast radius comp-foo), and spec-bundle-assembler
  modules
When main(["assist", "--changed=R-FOO-001", "--repo-root=<repo_root>",
  "--format=json"]) runs
Then it returns 0 and prints JSON whose predicted_blast_radius is
  ["comp-foo"] and whose degraded is true

Given the same repo_root
When main(["assist", "--changed", "R-FOO-001", "--repo-root",
  "<repo_root>", "--format", "text"]) runs
Then it returns 0 and prints text containing the warn finding's
  rule_id and "comp-foo"

Given the same repo_root plus faked generator and llm-endpoint modules,
  the llm-endpoint's complete returning a completeness response
  {"completeness_score": 0.7, "completeness_rationale": "AC missing"}
  and then a redundancy response {"redundancy_flags": []}
When main runs with "--model=fake-model" and "--format=json"
Then it returns 0, the faked llm-endpoint was called with model
  "fake-model", and the printed JSON has degraded false and
  completeness_score 0.7
And when main runs the same way with "--format=text"
Then the printed text contains "0.7"

Given a faked spec-linter returning a "fail"-severity finding
When main runs
Then it returns 1

Given no --changed, or --format=bogus, or an unknown argument, or
  "--changed" as the last argument with no value
When main runs
Then it returns 2
```
