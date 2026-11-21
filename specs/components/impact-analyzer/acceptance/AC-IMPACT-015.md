# AC-IMPACT-015

Covers: R-IMPACT-011
Kind: generated-test

```gherkin
Given a lint-clean git fixture with comp-foo and comp-qux
When main runs with each of these argument lists, <repo> its path:
  ["--changed", "comp-foo", "--format", "text", "comp-qux", "--repo-root", <repo>]
  ["--changed", "comp-foo", "-x", "--repo-root", <repo>]
  ["--repo-root", <repo>, "--changed"]
  ["--changed", "comp-foo", "--repo-root"]
  ["--changed", "comp-foo", "--format"]
  ["--changed", "comp-foo", "--format=yaml", "--repo-root", <repo>]
Then each returns 2, prints nothing to stdout, and its stderr's first
  line starts "usage error: "

When main(["--changed", "comp-foo", "comp-qux", "--format", "json",
  "--repo-root", <repo>]) runs
Then it returns 0 and stdout is one JSON document whose impacted
  component_ids are exactly ["comp-foo", "comp-qux"]
```
