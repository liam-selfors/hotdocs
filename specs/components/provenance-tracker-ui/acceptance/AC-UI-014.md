# AC-UI-014

Covers: R-UI-001
Kind: generated-test

```gherkin
Given a repo_root with a faked provenance-tracker whose check_readiness
  returns comp-foo passing and comp-bar failing, and a
  verification/corpus-graph.json listing both
When render_tracker_ui(out_dir, repo_root) runs and
  out_dir/index.html is read as text
Then "<style" occurs exactly once, after "<head" and before "</head>",
  the element's text holds ".tone-fail" and "--color-bg", and neither
  " style=" nor "<link" occurs in the file
```
