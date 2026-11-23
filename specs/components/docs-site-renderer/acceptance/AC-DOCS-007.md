# AC-DOCS-007

Covers: R-DOCS-007
Kind: generated-test

```gherkin
Given a repo_root whose verification/corpus-graph.json holds a valid
  graph, and an out directory
When cli.main runs ["--repo-root=<repo_root>", "--out=<out>"]
Then it returns 0 and out holds the rendered site

Given a repo_root with no verification/corpus-graph.json
When cli.main runs ["--repo-root=<repo_root>"]
Then it returns 1, and stderr holds exactly one line, which starts
  "error: " and ends "verification/corpus-graph.json is missing; run
  hotdocs corpus-graph build first" (one line, single spaces)

Given any repo_root
When cli.main runs ["--bogus"] or ["--out"]
Then each returns 2
```
