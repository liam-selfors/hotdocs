---
id: comp-merge-orchestrator-interface
title: Merge Orchestrator — Interface
status: draft
owners: [pipeline-team]
---

# Merge Orchestrator — Interface

## CLI

```
hotdocs merge --changed=<spec-id>... [--repo-root=<dir>] [--format=json|text]
```

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Merge succeeded — all gates passed, atomic commit made. |
| `1` | Merge blocked (R-MERGE-011). |
| `2` | Usage error. |

## Library

```
run_merge(changed_ids: list[str], repo_root: Path) -> MergeResult
```

## Data: `MergeResult`

```json
{
  "blocked": false,
  "components": {
    "comp-foo": {
      "cache_hit": false,
      "attempts": 1,
      "sample_index": 0,
      "verification": { "...": "a VerificationReport" },
      "cross_model_check": "not-run",
      "license_scan": { "...": "a LicenseScanResult" },
      "secret_scan": { "...": "a SecretScanResult" }
    }
  },
  "review_packet": { "...": "a ReviewPacket" },
  "block_reasons": []
}
```

`attempts` is the number of generation samples actually tried for that
component before either passing or exhausting `k` (R-MERGE-005/006).
