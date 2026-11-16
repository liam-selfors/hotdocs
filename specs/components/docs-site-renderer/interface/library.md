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
detail page, and one per edge, with no coordinates: a script embedded in
the page lays them out and filters them in the browser, so the Python
code computes no layout.

Implements: `specs/architecture/cli-conventions.md`
