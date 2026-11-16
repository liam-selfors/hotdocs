# AC-UI-004

Covers: R-UI-004
Kind: generated-test

```gherkin
Given a repo_root with a faked provenance-tracker (implementing both
  check_readiness and last_requirement_failures), a
  verification/corpus-graph.json whose nodes are comp-foo, comp-bar,
  P-ZERO-EDIT, and VAR-FOO-URL, with edges comp-foo->comp-bar
  (depends_on), comp-foo->P-ZERO-EDIT (realizes), and
  comp-foo->VAR-FOO-URL (uses_var), and a check_readiness result
  covering only comp-foo, comp-bar, and P-ZERO-EDIT
When render_tracker_ui runs
Then the snapshot's edges are exactly the depends_on and realizes
  edges, never the uses_var edge to a node outside the report, and
  after the call the only file created or changed anywhere under
  repo_root or out_dir is out_dir/index.html, ignoring any
  __pycache__ directory (Python's own import-time bytecode cache for
  the faked module, not a write by this component)
```
