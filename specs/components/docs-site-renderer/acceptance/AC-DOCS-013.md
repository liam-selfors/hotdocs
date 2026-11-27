# AC-DOCS-013

Covers: R-DOCS-001
Kind: generated-test

```gherkin
Given a CorpusGraph with nodes comp-alpha and comp-beta (components,
  comp-alpha's size_status "ok" and comp-beta's "over") and P-ALPHA
  (capability), and edges comp-alpha -> comp-beta (depends_on) and
  comp-alpha -> P-ALPHA (realizes)
When render_docs_site(graph, out_dir) runs and every .html file under
  out_dir is read as text
Then each holds "<style" exactly once, after "<head" and before
  "</head>", that element's text holds ".tone-ok" and "--color-bg",
  and no file holds " style=" or "<link"
```
