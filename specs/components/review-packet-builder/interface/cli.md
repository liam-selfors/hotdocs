# CLI

```
hotdocs review-packet build --changed=<spec-id>... [--repo-root=<dir>] [--format=markdown|json]
```

- `--changed` — spec ids changed in this PR (same input shape as
  `impact-analyzer`'s `--changed`).
- `--format` — `markdown` (default; what actually gets posted on a PR) or
  `json` (structured data for other tooling).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Packet built. |
| `1` | A required upstream result was missing. |
| `2` | Usage error. |
