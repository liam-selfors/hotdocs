# `component_size` (view)

```
component_id  TEXT  -- bare component name (e.g. "cache-manager"), no comp- prefix
word_count    BIGINT
```

One row per component (`R-GQE-006`): the words of every doc under its
directory but `testing.md`, which `corpus-graph-builder` shows (`R-GRAPH-009`). `component_id` is a
bare name, unlike every other view's `comp-`-prefixed ids (intentional,
`D13`).
