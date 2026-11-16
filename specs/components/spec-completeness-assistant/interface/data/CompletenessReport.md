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

A dataclass with these fields in this order and a `to_dict()` giving
the JSON form; its public members are exactly these fields and
`to_dict()`, none of which blocks, fails, exits or has a side effect.
`halted` and every other field are descriptive only (R-ASSIST-006).
`to_dict()` always holds every field, degraded or halted: it is the
R-ASSIST-008 hook, against which a calling tool records an accept or
override of `predicted_blast_radius`, `completeness_score` or a
`redundancy_flags` entry (named by its two ids).

`predicted_blast_radius` is the `component_id` of each `impacted` entry,
in `impacted`'s order, or `[]` when `precondition_error` is non-null.
`degraded` is `true` exactly when no `model` was given, halted or not; a
failed or unparseable model call leaves it `false`.

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
