# AC-SURF-006

Covers: R-SURF-005
Kind: generated-test

```gherkin
Given a repo_root whose comp-widget has gen/widget/widget.py containing
  "X = 1", the planted kinds fake (surface returns {"names": ["a", "b"]})
  and fakebad (surface raises RuntimeError("boom")), and the frontmatter
  line "assets: [nokind_q:static/x.js, fake:static/gone.js, fake:static/noiface.js, fakebad:static/bad.js, fake:static/app.js]",
  with files gen/widget/static/x.js, noiface.js, bad.js and app.js but
  no gone.js, and interface files interface/assets/x.js.md, gone.js.md,
  bad.js.md and app.js.md, each with a fenced block holding the one line
  "export function zz()"
When check_surface("comp-widget", repo_root) is called
Then ok is False and findings' kinds and messages are exactly, in order:
  asset_error "unknown asset kind: nokind_q",
  asset_error "static/gone.js: no such asset file",
  asset_error "static/noiface.js: no interface file interface/assets/noiface.js.md",
  asset_error "static/bad.js: surface failed: RuntimeError: boom",
  asset_name_missing "static/app.js has no zz, which its interface states"
```
