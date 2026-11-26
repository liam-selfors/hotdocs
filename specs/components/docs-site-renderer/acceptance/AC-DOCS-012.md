# AC-DOCS-012

Covers: R-DOCS-009
Kind: generated-test

```gherkin
Given a CorpusGraph with nodes comp-alpha and comp-beta (components)
  and P-ALPHA (capability), and edges comp-alpha -> comp-beta
  (depends_on) and comp-alpha -> P-ALPHA (realizes)
When render_docs_site(graph, out_dir) runs, out_dir/index.html is
  opened with browser.open, and "beta" is filled into the element with
  id "search"
Then of the li elements with class "node", only the one whose data-id
  is "comp-beta" is visible; after "" is filled in, all three are
  visible; console_errors() and blocked_requests() are both []
```
