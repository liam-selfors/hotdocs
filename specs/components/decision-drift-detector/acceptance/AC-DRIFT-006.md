# AC-DRIFT-006

Covers: R-DRIFT-004
Kind: generated-test

```gherkin
Given a repo_root with specs/ but no gen/ directory, and a copy of this
  component's code placed at <tool>/gen/decision-drift-detector/ beside
  a package-shaped fake at
  <tool>/gen/graph-query-engine/graph_query_engine/__init__.py that
  records every load_views call
When find_decision_drift runs against that repo_root, loaded from the
  copy
Then the fake's load_views was called exactly once, with that
  repo_root, graph-query-engine having been loaded from the tool root
```
