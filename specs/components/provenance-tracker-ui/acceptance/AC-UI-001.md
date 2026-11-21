# AC-UI-001

Covers: R-UI-001
Kind: generated-test

```gherkin
Given a repo_root with a faked provenance-tracker whose check_readiness
  returns a VerifyReport with one passing component comp-foo, and a
  verification/corpus-graph.json listing comp-foo
When render_tracker_ui(out_dir, repo_root) runs
Then out_dir contains exactly one file, index.html; its
  <script type="application/json" id="tracker-snapshot"> element
  parses as JSON equal to the returned TrackerSnapshot; it contains a
  node element with data-node-id="comp-foo"; and, outside the inlined
  text of static/app.js, it contains no "fetch(", no "XMLHttpRequest",
  no "WebAssembly", and no src= or href= attribute pointing at an
  external resource

Given a check_readiness result whose not_ready_reasons string contains
  "</script>"
When render_tracker_ui runs
Then the inlined tracker-snapshot block still parses as JSON equal to
  the returned TrackerSnapshot
```
