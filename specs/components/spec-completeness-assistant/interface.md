---
id: comp-spec-completeness-assistant-interface
title: Spec Completeness Assistant — Interface
status: draft
owners: [pipeline-team]
---

# Spec Completeness Assistant — Interface

## CLI

```
hotdocs assist --changed=<spec-id>... [--repo-root=<dir>] [--format=json|text]
```

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Report produced. Always `0` on a non-error run — this tool never fails a build; a low completeness score is reported, not a failure exit. |
| `1` | A hard-fail `spec-linter` finding was present (R-ASSIST-001) — reported, not blocking anything outside this CLI invocation itself. |
| `2` | Usage error. |

## Library

```
assist(changed_ids: list[str], repo_root: Path, model=None) -> CompletenessReport
```

`model` omitted (the default) runs in degraded mode, per R-ASSIST-007.

## Data: `CompletenessReport`

```json
{
  "lint_findings": [],
  "predicted_blast_radius": ["comp-foo"],
  "hint_previews": { "comp-foo": { "...": "a hint-mode SpecBundle-derived preview" } },
  "completeness_score": 0.9,
  "completeness_rationale": "...",
  "redundancy_flags": [],
  "degraded": false
}
```

`completeness_score`, `completeness_rationale`, and `redundancy_flags` are
`null`/empty with `degraded: true` when no model was configured
(R-ASSIST-007) — never silently omitted.
