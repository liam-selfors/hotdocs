# AC-ASSIST-009

Covers: R-ASSIST-009
Kind: generated-test

```gherkin
Given a repo_root with stand-ins for all four dependencies: lint
  returning one "warn" finding, a blast radius of comp-foo, and a check
  returning an object whose to_dict() is {"findings": []}
When main(["--changed=R-FOO-001", "--repo-root=<repo_root>",
  "--format=json"]) runs
Then it returns 0 and prints JSON whose predicted_blast_radius is
  ["comp-foo"] and whose degraded is true

Given the same repo_root
When main(["--changed", "R-FOO-001", "--repo-root",
  "<repo_root>", "--format", "text"]) runs
Then it returns 0 and prints text containing the warn finding's
  rule_id and "comp-foo"

Given the same repo_root, the llm-endpoint stand-in's complete returning
  a completeness response {"completeness_score": 0.7,
  "completeness_rationale": "AC missing"} to every prompt
When main runs with "--model=fake-model" and "--format=json"
Then it returns 0, the faked llm-endpoint was called with model
  "fake-model", and the printed JSON has degraded false and
  completeness_score 0.7
And when main runs the same way with "--format=text"
Then the printed text contains "0.7"

Given the same repo_root holding specs/components/foo/requirements/R-FOO-001.md,
  and lint returning a "fail"-severity finding whose file is
  "specs/components/foo/component.md"
When main(["--changed=R-FOO-001", "--repo-root=<repo_root>"]) runs
Then it returns 1

Given argv [], or ["serve", "--changed=R-FOO-001"] (a stray word is
  an unknown argument), or no --changed, or --format=bogus, or an unknown argument, or
  "--changed" as the last argument with no value
When main runs
Then it returns 2
```
