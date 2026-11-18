# AC-IMPACT-011

Covers: R-IMPACT-001
Kind: generated-test

```gherkin
Given a lint-clean corpus containing comp-foo and no comp-nope
When hotdocs impact --changed comp-nope --repo-root=<repo_root> runs
Then it exits with code 2, names comp-nope on stderr and prints nothing
  on stdout

Given the same corpus
When hotdocs impact --repo-root=<repo_root> runs with no --changed
Then it exits with code 2
```
