# Library

A package, `corpus_graph_builder/` (`__init__.py` plus `cli.py`, never a
flat module): `hotdocs-cli` runs `corpus_graph_builder.cli`'s `main`.
`__init__.py` exports:

```
build_corpus_graph(repo_root: Path) -> CorpusGraph
write_corpus_graph(graph: CorpusGraph, repo_root: Path) -> Path
```

`cli.py` exports `main(argv: list[str] | None = None) -> int`
(`interface/cli.md`, `R-GRAPH-007`).

`CorpusGraph` is a dataclass with attributes `nodes`, `edges` and
`aggregates` (`interface/data/CorpusGraph.md`), a `to_dict()` returning
that shape, and `to_json_bytes()` returning `json.dumps(to_dict(),
sort_keys=True, indent=2, ensure_ascii=True)` plus `"\n"`, UTF-8.
`write_corpus_graph` writes those bytes to
`<repo_root>/verification/corpus-graph.json`, creating `verification/`
if needed, and returns that path. `build_corpus_graph` writes nothing.

## graph-query-engine

`graph-query-engine` is loaded by file path (`R-GRAPH-010`), then used
on a fresh in-memory DuckDB connection: `INSTALL yaml FROM community`
(an error from it ignored), `LOAD yaml`, then `load_views(con,
repo_root)`. Tests use the real `graph-query-engine` and write no
stand-in for it: with no `gen/graph-query-engine/` under a test's
`repo_root` it comes from the tool root.

A test corpus therefore uses the files those views read, each opening
with a `---` YAML frontmatter block holding at least `id`, `title` and
`status`:

- a component: `specs/components/<slug>/component.md` with `id:
  comp-<slug>` and flow lists `depends_on: [comp-a]`, `realizes:
  [P-X]`, `uses_var: [VAR-Y]` (each may be `[]`), and `sealed: true` or
  `false`;
- a capability: `specs/product/<name>.md` with `id: P-<NAME>`;
- a var: `specs/vars/<name>.md` with `id: VAR-<NAME>`.

`component_size`'s `component_id` is the bare `<slug>`, not
`comp-<slug>`.

Implements: `specs/architecture/cli-conventions.md`
