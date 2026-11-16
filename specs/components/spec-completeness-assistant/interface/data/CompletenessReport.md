# `CompletenessReport`

```json
{
  "lint_findings": [
    { "rule_id": "R-LINT-003", "severity": "fail", "file": "specs/components/foo/component.md", "line": 12, "message": "depends_on references 'comp-bar', which does not exist" }
  ],
  "halted": true,
  "predicted_blast_radius": ["comp-foo"],
  "criterion_reviews": { "comp-foo": { "...": "spec-reviewer's ReviewReport.to_dict()" } },
  "completeness_score": 0.9,
  "completeness_rationale": "...",
  "redundancy_flags": [
    { "new_requirement": "R-FOO-005", "overlaps_with": "R-BAR-002", "rationale": "Both require retry exhaustion to surface as a distinct failure mode, worded differently." }
  ],
  "degraded": false
}
```

A dataclass with these fields in this order, with a `to_dict()` giving
the JSON form.

`lint_findings` entries are exactly `spec-linter`'s own `Finding` shape
(`interface/data/LintReport.md`'s `findings[]`, bundle-visible via
`depends_on`) — passed through unchanged, never restated or
summarized here: a finding that is a dict stays that dict, with no key
added or removed. `halted` is `true` exactly when `R-ASSIST-001` stopped
the run.

`completeness_score`, `completeness_rationale`, and `redundancy_flags` are
`null`/empty with `degraded: true` when no model was configured
(R-ASSIST-007) — never silently omitted. Each `redundancy_flags` entry is
`{new_requirement, overlaps_with, rationale}` (`R-ASSIST-005`):
`new_requirement` and `overlaps_with` are both `R-id`s, and `rationale`
is always present on a populated entry.
