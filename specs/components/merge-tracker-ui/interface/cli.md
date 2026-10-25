# CLI

```
hotdocs track ui build [--repo-root=<dir>] [--out=<dir>]
```

- `--out` — output directory for the rendered static page. Default:
  `.hotdocs/ui/` — local-only, same as the tracking data it renders
  (`SPEC_GUIDELINES.md` §1), deliberately **not** `dist/` the way
  `docs-site-renderer`'s output is, since that convention is for a CI
  build artifact meant to be published; this one never is.

How a developer opens the built page is the component's own open
question (`component.md`) — not resolved by this interface.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Page rendered to `--out` — including when `.hotdocs/tracking/` is empty or missing (R-UI-005: an explicit "no attempts yet" state is a successful render, not a failure). |
| `1` | A tracking record that exists failed to parse (corrupt JSON) — a real error, distinct from there simply being none yet. |
| `2` | Usage error. |
