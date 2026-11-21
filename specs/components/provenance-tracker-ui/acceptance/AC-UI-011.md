# AC-UI-011

Covers: R-UI-001
Kind: generated-test

```gherkin
Given a repo_root with a faked provenance-tracker whose check_readiness
  returns one passing component comp-foo, and a
  verification/corpus-graph.json listing comp-foo
When render_tracker_ui(out_dir, repo_root) runs
Then index.html contains exactly one <script type="module"> element
  and exactly two <script elements in all (that one and the
  tracker-snapshot JSON block); the module element's text is exactly
  A + "\ninit(document);\n", where A is the text of the file static/app.js
  in the directory holding the provenance_tracker_ui module (read
  as UTF-8, compared whole: this is the one place a test reads the
  asset's text, never to search it); and A occurs in index.html
  exactly once
```
