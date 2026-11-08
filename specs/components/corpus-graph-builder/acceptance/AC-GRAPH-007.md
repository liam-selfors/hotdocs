# AC-GRAPH-007

Covers: R-GRAPH-007
Kind: generated-test

```gherkin
Given a corpus with comp-a
When main(["build", "--repo-root=<repo_root>"]) runs, then
  main(["build", "--repo-root", "<repo_root>"]), then main(["build"])
  with the current directory changed to repo_root
Then each returns 0, writes verification/corpus-graph.json and prints
  its path

Given verification/a/.provenance.json holding "{not json"
When main(["build", "--repo-root=<repo_root>"]) runs
Then it returns 1

When main([]), main(["serve"]), main(["build", "--bogus"]) or
  main(["build", "--repo-root"]) runs
Then each returns 2 without raising
```
