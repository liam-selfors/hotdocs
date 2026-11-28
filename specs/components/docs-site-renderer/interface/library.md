# Library

A package, `docs_site_renderer/` (`__init__.py` plus `cli.py`, never a
flat module): `hotdocs-cli` runs `docs_site_renderer.cli`'s
`main(argv: list[str] | None = None) -> int`, which receives the tokens
after `build`, `hotdocs-cli`'s verb table stripping both verb words
(`interface/cli.md`).

```
render_docs_site(graph: CorpusGraph, out_dir: Path) -> None
```

A component's detail view (`R-DOCS-002`) is drawn from its node in
`corpus-graph-builder`'s `CorpusGraph` alone (`R-DOCS-004`): rendered
content from `documents`; each `R-id` and its live status from
`verification.requirement_results`; criteria by `kind` with their
results from `verification.criteria`; provenance from `provenance`;
size from `size_status`; exemptions from `sealed` and
`pinned_overrides`; owners from `owners`. A field that is `null` or
empty shows as absent, never as an error. Every value written into a
page is HTML-escaped.

The DAG view (`R-DOCS-001`) holds one element per node, linking to its
detail page, and one per edge, with no coordinates. The declared asset
`static/app.js` (`interface/assets/app.js.md`), at
`gen/docs-site-renderer/static/app.js` — `Path(__file__).parent.parent
/ "static" / "app.js"` from `docs_site_renderer/__init__.py` — is
inlined into `index.html` as `R-DOCS-001` states, and lays out
(`R-DOCS-008`) and filters (`R-DOCS-009`) them in the browser, so the
Python code computes no layout and holds no JavaScript. Reading the
asset is the component's own file, not a second data source under
`R-DOCS-004`.

Every page's only CSS is `comp-ui-style`'s `style_element()`, loaded as
`specs/architecture/visual-style.md` "Pages" states and written once in
each page's `<head>` (`R-DOCS-001`); it is the tool's own file, not a
data source under `R-DOCS-004`.

Implements: `specs/architecture/cli-conventions.md`, `specs/architecture/visual-style.md`
