# AC-DOCS-015

Covers: R-DOCS-008
Kind: generated-test

```gherkin
Given a CorpusGraph with nodes comp-alpha and comp-beta (components),
  P-ALPHA (capability) and VAR-X (var), and edges comp-alpha -> comp-beta
  (depends_on), comp-alpha -> P-ALPHA (realizes) and comp-beta -> VAR-X
  (uses_var)
When render_docs_site(graph, out_dir) runs and out_dir/index.html is
  opened with browser.open, then again with color_scheme="dark"
Then in each opening svg#dag holds exactly three line elements, with
  classes edge-depends-on, edge-realizes and edge-other, none with a
  stroke attribute; their three style("stroke") values are distinct;
  each has a contrast ratio of at least 3 with the body's
  style("background-color"), computed as
  specs/architecture/visual-style.md "Contrast" states from the
  rgb(r, g, b) values; and console_errors() is []
```
