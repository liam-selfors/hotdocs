# AC-LINT-039

Covers: R-LINT-034
Kind: generated-test

```gherkin
Given a corpus whose component "web" has depends_on [comp-kind-demo] and
  assets [demo:static/app.js], and specs/asset-kinds/demo.md has the
  seven sections of R-LINT-034, each with one line of text
When lint(None, repo_root) runs
Then there is no R-LINT-034 finding

Given the same corpus with assets [demo, Demo:a.js, demo:/abs.js,
  demo:a\b.js, demo:x/../y.js, demo:static/m.py]
When lint(None, repo_root) runs
Then specs/components/web/component.md has exactly these R-LINT-034 fail
  findings, in this order:
  "asset 'demo' is not <kind>:<path>",
  "asset 'Demo:a.js' is not <kind>:<path>",
  "asset 'demo:/abs.js': path must be relative with / separators",
  "asset 'demo:a\b.js': path must be relative with / separators",
  "asset 'demo:x/../y.js': path contains ..",
  "asset 'demo:static/m.py': path ends in .py"

Given the same corpus with "assets: demo:static/app.js", not a list
When lint(None, repo_root) runs
Then the only R-LINT-034 finding is
  "assets must be a list of <kind>:<path> strings"
```
