# Library

```
assist(changed_ids: list[str], repo_root: Path, model=None) -> CompletenessReport
```

`model` omitted (the default) runs in degraded mode, per R-ASSIST-007.
When present, dispatched via `llm-endpoint` (D18) — this component holds
no credential of its own.
