# AC-DOCS-015

Covers: R-DOCS-008
Kind: generated-test

Every edge below joins nodes in different columns and different rows, so
each drawn line is diagonal and has a box the browser driver can read (a
vertical or horizontal line has an empty box and never counts as
visible).

```gherkin
Given a CorpusGraph with nodes, in this order, P-ALPHA and P-BETA
  (capabilities), comp-alpha and comp-beta (components) and VAR-X (var),
  and edges comp-alpha -> P-BETA (kind depends_on), comp-beta -> P-ALPHA
  (kind realizes) and comp-beta -> VAR-X (kind uses_var)
When render_docs_site(graph, out_dir) runs and out_dir/index.html is
  opened with browser.open, then again with color_scheme="dark"
Then in each opening svg#dag holds exactly three line elements, found
  as css=svg#dag line.edge-depends-on, svg#dag line.edge-realizes and
  svg#dag line.edge-other, none with a stroke attribute; their three
  style("stroke") values are distinct; each has a contrast ratio of at
  least 3 with the body's style("background-color"), computed as
  specs/architecture/visual-style.md "Contrast" states from the
  rgb(r, g, b) values; and console_errors() is []
```
