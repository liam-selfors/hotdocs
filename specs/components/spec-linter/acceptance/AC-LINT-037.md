# AC-LINT-037

Covers: R-LINT-003
Kind: generated-test

```gherkin
Given specs/architecture/x.md with id arch-x and depends_on
  [arch-gone, arch-old, arch-ok], where no spec has id arch-gone,
  arch-old's status is deprecated and arch-ok's is draft
When lint(None, repo_root) runs
Then specs/architecture/x.md has exactly two R-LINT-003 fail findings,
  one naming arch-gone with "does not exist" in its message and one
  naming arch-old, and none naming arch-ok
```
