# `edges` (view)

```
source_id  TEXT  -- a comp-id (depends_on/realizes/uses_var/depends_on_guarantees), or an AC-id/CS-id (covers)
target_id  TEXT  -- the id named in the frontmatter list entry, or the Covers: line's value
edge_type  TEXT  -- one of: depends_on, realizes, uses_var, depends_on_guarantees, covers
```

One row per `(source_id, target_id, edge_type)` (`R-GQE-002`). A
`covers` edge's `source_id` is the criterion itself (an `AC-id` or a
bare `CS-id`), not the component that owns it — joining through
`nodes.owner_component_id` recovers that when needed.
