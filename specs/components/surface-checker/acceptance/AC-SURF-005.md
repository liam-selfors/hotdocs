# AC-SURF-005

Covers: R-SURF-005
Kind: generated-test

```gherkin
Given a repo_root whose comp-widget has gen/widget/widget.py containing
  "X = 1", the frontmatter line "assets: [fake:static/app.js]", a file
  gen/widget/static/app.js, the planted kind fake whose surface returns
  {"names": ["a", "b"]}, and an interface/assets/app.js.md whose first
  fenced block has the lines "export function zeta(y, z)",
  "export function a(x)", "export const b", "export function c()" and
  "export function c(q)"
When check_surface("comp-widget", repo_root) is called
Then ok is False and findings is exactly, in order,
  {"kind": "asset_name_missing", "message": "static/app.js has no c, which its interface states"}
  and
  {"kind": "asset_name_missing", "message": "static/app.js has no zeta, which its interface states"}

Given the same repo_root whose app.js.md fenced block has only the line
  "export function a(x)"
When check_surface("comp-widget", repo_root) is called
Then ok is True and findings is []
```
