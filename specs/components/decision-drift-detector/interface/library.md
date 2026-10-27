# Library

```
find_decision_drift(repo_root: Path) -> DriftReport
```

A pure function over the filesystem state and git history at
`repo_root` — reads, never writes; no model calls. Walks the live
corpus once, resolving each `D<N>` citation's commit ancestry against
`graph-query-engine`'s `decision_lineage` view.
