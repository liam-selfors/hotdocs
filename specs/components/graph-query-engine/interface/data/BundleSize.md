# `bundle_size` (view)

```
component_id         TEXT    -- bare component name, as in component_size
generator_words      BIGINT
criterion_words_max  BIGINT
```

One row per component (`R-GQE-009`), read by `size-checker`
(`R-SIZE-001`), never recomputed.
