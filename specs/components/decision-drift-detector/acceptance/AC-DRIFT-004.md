# AC-DRIFT-004

Covers: R-DRIFT-004
Kind: generated-test

```gherkin
Given a repo_root whose own gen/graph-query-engine/ holds a fake
  module recording every load_views call, and this component's own
  code lives somewhere else entirely (a different directory, not
  under repo_root)
When find_decision_drift runs against that repo_root
Then the fake's load_views was called exactly once, proving
  graph-query-engine was resolved relative to repo_root, never to
  this component's own file location
```
