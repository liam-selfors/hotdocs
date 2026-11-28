# AC-UI-012

Covers: R-UI-010
Kind: generated-test

```gherkin
Given a repo_root with a faked provenance-tracker whose check_readiness
  returns comp-foo passing and comp-bar failing, and a
  verification/corpus-graph.json listing both
When render_tracker_ui(out_dir, repo_root) runs, out_dir/index.html is
  opened with browser.open, and the button "failing" is clicked
Then the li.node elements' texts that are visible are exactly those
  holding comp-bar, and after the button "all" is clicked both are
  visible; console_errors() and blocked_requests() are both []
```
