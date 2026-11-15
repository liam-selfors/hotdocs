# AC-DOCS-007

Covers: R-DOCS-007
Kind: generated-test

```gherkin
Given a repo_root whose verification/corpus-graph.json holds a valid
  graph, and an out directory
When cli.main runs ["build", "--repo-root=<repo_root>", "--out=<out>"]
Then it returns 0 and out holds the rendered site

Given a repo_root with no verification/corpus-graph.json
When cli.main runs ["build", "--repo-root=<repo_root>"]
Then it returns 1

Given any repo_root
When cli.main runs ["build", "--bogus"], ["build", "--out"], or
  ["render"]
Then each returns 2
```
