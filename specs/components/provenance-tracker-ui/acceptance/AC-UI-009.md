# AC-UI-009

Covers: R-UI-009
Kind: generated-test

```gherkin
Given a repo_root with a faked provenance-tracker and a
  corpus-graph.json
When main(["track", "ui", "build", "--repo-root=<repo_root>",
  "--out=<dir>", "--changed=comp-foo,comp-bar"]) runs
Then it returns 0, prints the path of <dir>/index.html, and the faked
  check_readiness received changed_ids ["comp-foo", "comp-bar"]

Given the same repo_root
When main(["track", "ui", "build", "--repo-root", "<repo_root>",
  "--out", "<dir>", "--changed", "comp-foo", "--model", "fake-model",
  "--seed", "3"]) runs
Then it returns 0, writes <dir>/index.html, and the faked
  check_readiness received changed_ids ["comp-foo"], model
  "fake-model", and seed 3

Given no --out argument
When main runs build
Then the page is written to <repo_root>/.hotdocs/ui/index.html

Given a corpus-graph.json containing invalid JSON
When main runs build
Then it returns 1

Given no verification/corpus-graph.json, or a faked check_readiness
  that raises ValueError, or an unknown argument
When main runs build
Then it returns 2

Given a valid repo_root
When main runs with ["track", "ui", "serve"], or with any of
  "--changed", "--repo-root", "--out", "--model", "--seed" as the last
  argument with no value
Then it returns 2
```
