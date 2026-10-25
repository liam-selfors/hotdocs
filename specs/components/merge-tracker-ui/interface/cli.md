# CLI

```
hotdocs track ui build [--repo-root=<dir>] [--out=<dir>]
hotdocs track ui serve [--repo-root=<dir>] [--out=<dir>] [--port=<n>]
```

- `--out` — output directory for the rendered static page. Default:
  `.hotdocs/ui/` — local-only, same as the tracking data it renders
  (`SPEC_GUIDELINES.md` §1), deliberately **not** `dist/` the way
  `docs-site-renderer`'s output is, since that convention is for a CI
  build artifact meant to be published; this one never is.

`serve` (`R-UI-006`) starts a trivial local static-file server exposing
only `--out` (the built page) and `.hotdocs/tracking/` — the documented
way to open this component's output, resolving `component.md`'s former
open question. `--port` defaults to an ephemeral port; the command
prints the URL it bound to. The server does not build the page itself —
run `build` first (or `serve` MAY run it implicitly if `--out` doesn't
exist yet; either way, `serve` builds nothing beyond that).

**Exit codes (`build`):**

| Code | Meaning |
| --- | --- |
| `0` | Page rendered to `--out` — including when `.hotdocs/tracking/` is empty or missing (R-UI-005: an explicit "no attempts yet" state is a successful render, not a failure). |
| `1` | A tracking record that exists failed to parse (corrupt JSON) — a real error, distinct from there simply being none yet. |
| `2` | Usage error. |

**Exit codes (`serve`):** `0` on clean shutdown (Ctrl-C); `2` on usage
error (e.g. `--port` already bound). Runs in the foreground until
stopped — no daemonizing, no background process left behind.
