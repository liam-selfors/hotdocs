# `component_size` (view)

```
component_id  TEXT  -- bare component name (e.g. "cache-manager"), no comp- prefix
word_count    BIGINT
```

One row per component (`R-GQE-006`): the words of every doc under its
directory but `testing.md`, which `corpus-graph-builder` shows (`R-GRAPH-009`). `component_id`'s
bare-name format (unlike every other view's `comp-`-prefixed ids) is
inherited unchanged from `spec-linter`'s own existing lookup key
(`D13`) — a pre-existing inconsistency, not introduced here, and not
fixed here since doing so would also require changing `spec-linter`'s
own internal `corpus.components` dict key format for no behavioral
benefit.
