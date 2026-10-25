# Library

```
render_tracker_ui(out_dir: Path) -> None
```

A build-time step only — reads nothing at build time (unlike
`docs-site-renderer`'s `render_docs_site(graph: CorpusGraph, ...)`, which
takes the data to render as a parameter). This component's data read
happens **in the browser, at view time**, via DuckDB-WASM querying
`.hotdocs/tracking/*.json` directly — the built page is static HTML/JS/WASM
with no data baked in, so it always reflects whatever tracking records
exist when it's opened, not whatever existed when it was built.
