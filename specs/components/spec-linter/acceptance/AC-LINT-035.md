# AC-LINT-035

Covers: R-LINT-033
Kind: generated-test

```gherkin
Given components a and b, each with a depends_on naming a component
  that does not exist
When lint([Path("specs/components/a")], repo_root) runs
Then every finding's file is under specs/components/a/, and an
  R-LINT-003 finding for specs/components/a/component.md is among them

When lint([Path("specs/components/b/component.md")], repo_root) runs
Then every finding's file is specs/components/b/component.md, and an
  R-LINT-003 finding is among them
```
