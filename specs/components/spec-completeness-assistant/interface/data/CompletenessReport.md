# `CompletenessReport`

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
