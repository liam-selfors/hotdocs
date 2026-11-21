# AC-DOCS-011

Covers: R-DOCS-001
Kind: generated-test

```gherkin
Given a CorpusGraph with nodes comp-foo (component) and P-FOO
  (capability) and one realizes edge comp-foo -> P-FOO
When render_docs_site(graph, out_dir) runs
Then out_dir/index.html contains "<script" exactly once, as
  <script type="module">, and that element's text is exactly
  A + "\ninit(document);\n", where A is the text of the file
  static/app.js in the parent of the directory holding the
  docs_site_renderer package's __init__.py (read as UTF-8 and compared
  whole: this is the one place a test reads the asset's text, never to
  search it); index.html also contains an element with id "search", an
  svg element with id "dag", and two li elements with class "node"
  whose data-id are "P-FOO" then "comp-foo"; and no other .html file
  under out_dir contains "<script"
```
