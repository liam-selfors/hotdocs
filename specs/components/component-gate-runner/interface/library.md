# Library

```
run_component_gates(
    component_id: str, repo_root: Path, model: str, seed: int = 0,
    llm_backend=None, retry_feedback: list[str] | None = None,
) -> ComponentPipelineResult
```

`model`/`seed`/`llm_backend` are this component's own parameters now
(`D86`) — it wires the real `test_author`/`judge` closures itself
(`R-GATE-002`), capturing them here rather than receiving
already-wired callables from a caller. `retry_feedback` (`R-GATE-003`,
`D3`) is this one component's own `R-id` list, supplied directly by
whoever invokes this call — never derived or defaulted internally.

CLI: see `interface/cli.md`. Invoked directly by a developer
(`hotdocs generate`, `D91`) — no component calls this one on a
developer's behalf (`D86`/`D87`).
