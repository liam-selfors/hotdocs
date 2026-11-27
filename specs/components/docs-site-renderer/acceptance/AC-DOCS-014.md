# AC-DOCS-014

Covers: R-DOCS-002
Kind: generated-test

```gherkin
Given a CorpusGraph with nodes comp-alpha and comp-beta (components,
  comp-alpha's size_status "ok" and comp-beta's "over") and P-ALPHA
  (capability), and edges comp-alpha -> comp-beta (depends_on) and
  comp-alpha -> P-ALPHA (realizes)
When render_docs_site(graph, out_dir) runs and
  out_dir/nodes/comp-alpha.html and out_dir/nodes/comp-beta.html are
  each opened with browser.open, then again
  with color_scheme="dark"
Then comp-alpha's page has exactly one span.size element, with class
  tone-ok, and comp-beta's exactly one, with class tone-fail, those two elements'
  style("border-left-color") values differ in each scheme, and on every
  page the body's style("color") has a contrast ratio of at least 4.5
  with its style("background-color"), computed as
  specs/architecture/visual-style.md "Contrast" states from the
  rgb(r, g, b) values
And each page's body style("background-color") differs between the two
  schemes, and console_errors() is [] on every page
```
