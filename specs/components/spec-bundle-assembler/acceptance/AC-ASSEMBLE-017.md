# AC-ASSEMBLE-017

Covers: R-ASSEMBLE-015
Kind: generated-test

```gherkin
Given the library's test fixture under a fresh repo_root with no gen/
  directory at all
When assemble and assemble_criterion run for comp-foo
Then both succeed, linting and reading the corpus with the spec-linter
  and graph-query-engine found under the tool root, and
  repo_root/gen still does not exist afterwards
```
