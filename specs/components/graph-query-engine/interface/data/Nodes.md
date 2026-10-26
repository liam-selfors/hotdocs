# `nodes` (view)

```
id                  TEXT   -- the spec id itself (R-id, AC-id, G-id, comp-id, P-id, VAR-id, or a bare CS-id)
title               TEXT   -- NULL for guarantee/requirement/acceptance/capability_scenario kinds
status              TEXT   -- NULL for the same four kinds (no frontmatter to read it from)
kind                TEXT   -- one of: component, capability, var, guarantee, requirement, acceptance, capability_scenario
owner_component_id  TEXT   -- comp-id that owns this node; NULL for component/capability/var/capability_scenario kinds
```

One row per spec id in the corpus (`R-GQE-001`). `title`/`status` are
only ever populated for the three frontmatter-bearing kinds
(`component`/`capability`/`var`) — the other four kinds carry no
frontmatter at all (D15), so those columns stay `NULL` by construction,
not by omission.
