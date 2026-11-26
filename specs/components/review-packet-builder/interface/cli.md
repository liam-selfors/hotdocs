# CLI

```
hotdocs review-packet build --changed=<spec-id>... [--repo-root=<dir>] [--format=markdown|json]
```

- `--changed` — spec ids changed in this PR (same input shape as
  `impact-analyzer`'s `--changed`).
- `--format` — `markdown` (default) or `json`.

`argv` begins `["review-packet", "build"]`. Every flag takes its value as
`--flag=value` or as the next argument (`--flag value`); `--changed` may
repeat; a flag given last with no value is a usage error.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Packet built. |
| `1` | A required upstream result was missing. |
| `2` | Usage error. |
