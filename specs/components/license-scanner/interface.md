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
  "similarity_score": 0.55,
  "block_threshold": 0.70,
  "blocked": false,
  "matches": [
    { "reference_id": "ref-123", "license_family": "gpl-3.0", "risk_tier": "high", "score": 0.55 }
  ],
  "notified": true,
  "cache_hit": false
}
```

`matches` is non-empty only when `similarity_score` is above a reporting
floor (always populated on a flagged result; may be empty on a clean one).
Each match entry carries its reference's own `license_family` and
`risk_tier` — curated with the reference corpus, not computed here.
`blocked` is `similarity_score >= block_threshold` — confidence only.
`notified` is `(blocked) OR (any match's risk_tier == "high")`, **and**
`VAR-COMPLIANCE-WEBHOOK-URL` is configured — deliberately not a function of
`similarity_score` against a second threshold; the worked example above is
a *below-block-threshold, high-risk-tier* match that still notifies, which
is exactly the case a same-scale severity threshold couldn't express.
