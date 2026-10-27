# Library

```
run_merge(changed_ids: list[str], repo_root: Path, retry_feedback: dict[str, list[str]] | None = None) -> MergeResult
```

`retry_feedback` maps `component_id` to an `R-id` list (R-MERGE-022,
`D3`) — a caller-supplied input only; this component never computes
one itself.
