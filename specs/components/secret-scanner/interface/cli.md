# CLI

```
hotdocs secret-scan [--repo-root=<dir>] [--format=json|text]
hotdocs secret-scan precommit [--files=<path>...] [--repo-root=<dir>] [--format=json|text]
```

- First form — full scan of `specs/`, `gen/`, and `verification/`, the
  merge-gate invocation (R-SECRET-001–007, cache-aware).
- `precommit` — lightweight invocation (R-SECRET-008), scoped to
  `--files` (defaults to the files staged/pending in the local git state
  when omitted); no `cache-manager` dependency.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Clean. |
| `1` | Flagged — merge blocked (full-scan form) or commit/push should be stopped (precommit form). |
| `2` | Usage error. |
