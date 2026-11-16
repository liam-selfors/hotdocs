# AC-DOCS-008

Covers: R-DOCS-002
Kind: generated-test

```gherkin
Given a component node whose documents hold the text
  "<script>alert(1)</script> & more", and a second component node whose
  verification and provenance are null and whose owners is empty
When render_docs_site runs
Then the first node's detail view contains "&lt;script&gt;" and
  "&amp; more" and never the raw "<script>alert(1)</script>", and the
  second node's detail view renders without error
```
