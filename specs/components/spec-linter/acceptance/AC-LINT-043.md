# AC-LINT-043

Covers: R-LINT-037
Kind: generated-test

```gherkin
Given testing.md's clean corpus written with write_corpus(repo_root,
  changes) where changes adds
  "specs/components/ghost/requirements/R-GHOST-001.md" with the text
  "# R-GHOST-001\n\n**R-GHOST-001** — x.\n"
When lint(None, repo_root) runs
Then it returns without raising and its findings are exactly one,
  rule_id "R-LINT-037", severity "fail", file "specs/components/ghost/",
  line 1, message "specs/components/ghost/ has no component.md"
```
