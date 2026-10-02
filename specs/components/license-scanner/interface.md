---
id: comp-license-scanner-interface
title: License Scanner — Interface
status: draft
owners: [pipeline-team]
---

# License Scanner — Interface

## CLI

```
hotdocs license-scan <component-id> [--repo-root=<dir>] [--format=json|text]
```

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Clean (below block threshold). |
| `1` | Flagged (at or above block threshold) — merge blocked. |
| `2` | Usage error. |

## Library

```
scan(component_id: str, repo_root: Path) -> LicenseScanResult
```

## Data: `LicenseScanResult`

```json
{
  "component_id": "comp-foo",
  "gate_version": "license_scanner@3.1.0",
  "similarity_score": 0.12,
  "block_threshold": 0.70,
  "severity_threshold": 0.90,
  "blocked": false,
  "notified": false,
  "matches": [],
  "cache_hit": false
}
```

`matches` is non-empty only when `similarity_score` is above a reporting
floor (always populated on a flagged result; may be empty on a clean one).
`blocked` is `similarity_score >= block_threshold`. `notified` is
`similarity_score >= severity_threshold` **and** `VAR-COMPLIANCE-WEBHOOK-URL`
is configured.
