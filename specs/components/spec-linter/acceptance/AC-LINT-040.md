# AC-LINT-040

Covers: R-LINT-034
Kind: generated-test

```gherkin
Given a corpus whose component "web" has depends_on [] and assets
  [nosuchkind-x9:a.js, demo:b.js], and specs/architecture/asset-kind-demo.md has
  the seven sections of R-LINT-034 except that "## Surface" is absent
  and "## Strength check" is followed directly by "## Test author
  guidance"
When lint(None, repo_root) runs
Then specs/components/web/component.md has exactly these R-LINT-034 fail
  findings, in this order:
  "asset kind 'nosuchkind-x9' has no definition",
  "asset kind 'demo' definition lacks section 'Surface'",
  "asset kind 'demo' definition has empty section 'Strength check'",
  "asset kind 'demo' is defined in this repository; depends_on must list comp-kind-demo"
```
