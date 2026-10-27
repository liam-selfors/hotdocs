# Library

```
find_decision_drift(repo_root: Path) -> DriftReport
find_decision_impact(repo_root: Path, decision_id: str) -> DecisionImpactReport
```

Both pure functions over the filesystem state and git history at
`repo_root` — reads, never writes; no model calls.
`find_decision_drift` walks the live corpus once, resolving each
`D<N>` citation's commit ancestry against `graph-query-engine`'s
`edges` (`supersedes` chain) and `decision_lineage`
(`last_ratified_commit`). `find_decision_impact` answers a different,
forward-looking question — usable on a decision before it is ever
ratified — by walking `edges` backward from `decision_id` and
collecting every live citation of it, unfiltered by staleness.
