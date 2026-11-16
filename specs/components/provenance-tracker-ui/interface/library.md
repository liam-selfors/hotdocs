# Library

```
render_tracker_ui(
    out_dir: Path, repo_root: Path, changed_ids: list[str] | None = None,
    model: str | None = None, seed: int = 0, llm_backend=None,
) -> TrackerSnapshot
```

Calls `provenance-tracker`'s `check_readiness(repo_root, changed_ids,
model, seed, llm_backend)` exactly once, passing every argument
straight through, then writes one self-contained `out_dir/index.html`
(`R-UI-001`) and returns the `TrackerSnapshot` it inlined
(`interface/data/TrackerSnapshot.md`). `changed_ids` omitted means the
whole-corpus view; present means the blast-radius view (`R-UI-007`).
The `ValueError` `provenance-tracker`'s `check_readiness` raises for a
capability provenance miss with no `model` propagates unchanged.

Topology comes from `<repo_root>/verification/corpus-graph.json`
(`corpus-graph-builder`'s committed output); attempt history from
`<repo_root>/.hotdocs/attempts/<component_id>/*.json` (`AttemptRecord`,
`provenance-tracker`'s own data type), and retry-feedback suggestions
from `provenance-tracker`'s `last_requirement_failures(component_id,
repo_root)`, called once for every component whose status is
`failing` or `missing`. Any stand-in for `provenance-tracker` must
therefore provide both `check_readiness` and
`last_requirement_failures`. A missing
`.hotdocs/attempts/` directory is normal, not an error (`R-UI-005`); a
file there that exists but fails to parse as JSON raises `ValueError`.

Implements: `specs/architecture/cli-conventions.md`
