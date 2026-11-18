# AC-LINT-036

Covers: R-LINT-014
Kind: generated-test

```gherkin
Given specs/glossary.md and specs/glossary-billing.md, and a file under
  specs/architecture/ whose body records a bounded-context split of the
  glossary
When lint(None, repo_root) runs
Then the report has no R-LINT-014 finding

Given only specs/glossary.md and no such architecture file
When lint(None, repo_root) runs
Then the report has no R-LINT-014 finding
```
