# AC-REVIEW-008

Covers: R-REVIEW-008
Kind: generated-test

```gherkin
Given a lint-clean synthetic corpus whose component foo's component.md
  frontmatter also has the line
  "assets: [javascript:static/app.js, javascript:static/b.js]",
  and which has the file specs/components/foo/interface/assets/b.js.md
  holding "# Asset b.js"
When check(["AC-FOO-001"], repo_root) is called with no model
Then findings holds exactly one finding, with criterion_id "comp-foo",
  kind "asset_interface_missing", token "static/app.js" and message
  "`static/app.js` has no interface file specs/components/foo/interface/assets/app.js.md"

Given the same corpus with the file
  specs/components/foo/interface/assets/app.js.md added
When check(["comp-foo"], repo_root) is called with no model
Then findings is empty

Given the first corpus with its assets line changed to
  "assets: [javascript:static/app.js, broken]" (the item "broken" is a
  fail-severity lint finding)
When check(["comp-foo"], repo_root) is called with no model
Then lint_findings holds at least one finding with severity "fail",
  criteria_checked is empty, and findings holds exactly one finding, with
  kind "asset_interface_missing" and token "static/app.js"

Given a lint-clean synthetic corpus whose component.md has no assets line
When check(["comp-foo"], repo_root) is called with no model
Then findings is empty
```
