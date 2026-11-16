# CLI

```
hotdocs provenance write <component-id> [--repo-root=<dir>]
```

`main(argv)` receives `argv` beginning exactly `["provenance", "write",
<component-id>, ...]`, the verb words kept (`D184`'s dispatcher strips
none). `argv` not beginning `["provenance", "write"]` is a usage error.
`--repo-root` defaults to the current directory and takes its value as
`--repo-root=<dir>` or as the next argument; `--repo-root` given last with
no value, any other `--` flag, or a second positional argument is a usage
error.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Manifest written to both required locations. |
| `1` | A required upstream result (e.g. `verifier-orchestrator`'s report) was missing — this component cannot invent what it didn't receive. |
| `2` | Usage error. |
