---
id: comp-review-packet-builder-interface
title: Review Packet Builder — Interface
status: draft
owners: [pipeline-team]
---

# Review Packet Builder — Interface

## CLI

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

## Library

```
build_review_packet(changed_ids: list[str], repo_root: Path) -> ReviewPacket
```

## Data: `ReviewPacket`

```json
{
  "spec_diff": "<unified diff text>",
  "changed_requirements": ["R-FOO-001"],
  "regenerated_components": ["comp-foo"],
  "verification_results": { "comp-foo": { "...": "a VerificationReport" } },
  "compliance_flags": { "license_scan": [], "secret_scan": [] },
  "cache_hit_status": { "comp-foo": false },
  "exemption_changes": { "sealed": [], "pinned_overrides": [] },
  "residual_risk": []
}
```
