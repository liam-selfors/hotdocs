# `component_docs` (view)

```
id          TEXT  -- comp-id
title       TEXT
status      TEXT
...         --  every other component.md frontmatter field (depends_on, realizes, etc.), passed through as-is
body        TEXT  -- component.md's full raw text, frontmatter included
```

One row per component (`R-GQE-003`). The data layer, not a rendered
view — answers "what does this component's frontmatter and prose say,"
not "what should a human see" (`docs-site-renderer`'s job).
