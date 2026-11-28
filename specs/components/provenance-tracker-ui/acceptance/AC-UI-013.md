# AC-UI-013

Covers: R-UI-002
Kind: generated-test

```gherkin
Given a repo_root with a faked provenance-tracker whose check_readiness
  returns comp-foo passing and comp-bar failing, and a
  verification/corpus-graph.json listing both
When render_tracker_ui(out_dir, repo_root) runs and out_dir/index.html
  is opened with browser.open, then again with color_scheme="dark"
Then in each opening the li.node element holding comp-foo has class
  tone-ok and the one holding comp-bar has class tone-fail, their
  style("border-left-width") is "4px", their
  style("border-left-color") values differ, and each of those colours
  has a contrast ratio of at least 3 with the body's
  style("background-color"), computed as
  specs/architecture/visual-style.md "Contrast" states from the
  rgb(r, g, b) values
And the body's style("background-color") differs between the two
  openings, and console_errors() is [] in both
```
