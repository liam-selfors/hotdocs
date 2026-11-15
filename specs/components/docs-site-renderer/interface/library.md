# Library

A package, `docs_site_renderer/` (`__init__.py` plus `cli.py`, never a
flat module): `hotdocs-cli` runs `docs_site_renderer.cli`'s
`main(argv: list[str] | None = None) -> int`, which receives the tokens
from `build` on (`interface/cli.md`).

```
render_docs_site(graph: CorpusGraph, out_dir: Path) -> None
```
