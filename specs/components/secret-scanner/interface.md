---
id: comp-secret-scanner-interface
title: Secret Scanner — Interface
status: draft
owners: [pipeline-team]
---

# Secret Scanner — Interface

## CLI

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

## Library

```
scan(repo_root: Path) -> SecretScanResult
scan_files(paths: list[Path]) -> SecretScanResult
```

`scan` is the full, cache-aware form. `scan_files` is the precommit form —
no cache lookup, no `gate_version` dependency, since it's meant to run
before a commit exists to key anything on.

## Data: `SecretScanResult`

```json
{
  "scope": "full",
  "gate_version": "secret_scanner@2.0.0",
  "flagged": false,
  "severity_threshold_crossed": false,
  "notified": false,
  "matches": [],
  "cache_hit": false
}
```

`scope` is `"full"` or `"precommit"`. `gate_version` and `cache_hit` are
only meaningful for `scope: "full"` — a `precommit` result always has
`cache_hit: false` and MAY omit `gate_version` entirely, since R-SECRET-008
explicitly has no cache dependency.
