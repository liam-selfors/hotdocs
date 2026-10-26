# `CompletenessReport`

```json
{
  "lint_findings": [],
  "predicted_blast_radius": ["comp-foo"],
  "hint_previews": { "comp-foo": { "...": "a hint-mode SpecBundle-derived preview" } },
  "completeness_score": 0.9,
  "completeness_rationale": "...",
  "redundancy_flags": [
    { "new_requirement": "R-FOO-005", "overlaps_with": "R-BAR-002", "rationale": "Both require retry exhaustion to surface as a distinct failure mode, worded differently." }
  ],
  "degraded": false
}
```

`completeness_score`, `completeness_rationale`, and `redundancy_flags` are
`null`/empty with `degraded: true` when no model was configured
(R-ASSIST-007) — never silently omitted. Each `redundancy_flags` entry is
`{new_requirement, overlaps_with, rationale}` (`R-ASSIST-005`):
`new_requirement` and `overlaps_with` are both `R-id`s, and `rationale`
is always present on a populated entry — there is no "fired but
unexplained" state, since an entry exists here only because a real
judgment call actually flagged it.
