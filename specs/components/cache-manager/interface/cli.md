# CLI

```
python -m cache_manager inspect --spec-bundle-hash=<h> --gate-inputs-hash=<h> --gate-version=<v> --model-pin=<p> [--repo-root=<dir>]
python -m cache_manager stats [--repo-root=<dir>]
```

`main(argv: list[str] | None = None) -> int` takes the tokens after
`python -m cache_manager` (no `hotdocs` verb routes here) and returns the
exit code. Each flag also takes the space form (`--model-pin <p>`).
Flags are never abbreviated: `--model=m` is an unknown flag, not
`--model-pin`. Every `inspect` flag but `--repo-root` is required.
`--repo-root` defaults to the current directory. Output is one line of
JSON on stdout:

- `inspect` — `{"result": "miss"}`, or on a hit
  `{"result": "hit", "gate_type": <t>, "stored_at": <ts>}`; never the
  payload.
- `stats` — `{"entry_count": <n>}`, the number of entries the local store
  currently holds (`0` when `VAR_CACHE_STORE_URL` is set).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Command completed; a miss is an answer, not a failure. |
| `2` | Usage error: no subcommand, an unknown one, or a missing or unknown flag. |
