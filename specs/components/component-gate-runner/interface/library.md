# Library

```
run_component_gates(component_id: str, repo_root: Path, test_author, judge,
                     retry_feedback: list[str] | None = None) -> ComponentPipelineResult
```

`test_author` and `judge` are already-wired, single-`bundle`-argument
callables (`R-GATE-002`) — this component never constructs them, only
passes them through to `verifier-orchestrator`. `retry_feedback`
(`R-GATE-003`, `D3`) is this one component's own `R-id` list, already
resolved out of `merge-orchestrator`'s `component_id`-keyed map
(`R-MERGE-022`) before this call — never a map itself.

No CLI — this component is never invoked directly by a human, only by
`merge-orchestrator`, the same posture `capability-scenario-verifier`
already takes.
