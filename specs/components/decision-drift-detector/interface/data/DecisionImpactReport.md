# `DecisionImpactReport`

```json
{
  "decision_id": "D17",
  "dependent_decisions": ["D31"],
  "citing_files": [
    "specs/components/provenance-tracker/component.md",
    "specs/components/provenance-tracker/requirements/R-TRACK-009.md"
  ]
}
```

`dependent_decisions` is the transitive closure of every decision
whose `supersedes` or `builds_on` edge points at `decision_id`
(`R-DRIFT-003`) — empty if nothing depends on it yet.
`citing_files` is every live spec file citing `decision_id`, not
filtered by staleness — this report answers "what would need review,"
`DriftReport` answers "what already looks stale."
