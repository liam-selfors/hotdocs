# CLI

```
hotdocs verify [--changed=<spec-id>...] [--repo-root=<dir>] [--format=json|text]
hotdocs track feedback <component-id> [--repo-root=<dir>]
```

`hotdocs verify` (`R-TRACK-009`/`010`, `D88`) is the canonical "will a
merge pass" command — omitting `--changed` checks the whole corpus,
supplying it checks just that blast radius. Exit `0` means `ready` is
`true`; exit `1` means at least one component or capability in scope
is not ready, with `not_ready_reasons` printed (`--format=text`, the
default) or available as structured data (`--format=json`). This
command confirms readiness; it does not gate anything itself — nothing
requires it to be run before a commit (`D87`).

`track feedback` (`R-TRACK-008`, `D3`) prints the named component's
most recent failing `R-id`s, comma-separated, ready to paste into
`hotdocs generate <component-id> --retry-feedback=...` (`D86`) — or
nothing, if no failed attempt exists. It does not pass anything
anywhere itself; it only answers "what would I pass," leaving whether
to pass it to the developer running the command.

There is no `hotdocs track write` CLI command — `write_attempt_record`
is invoked by `component-gate-runner` directly, never run standalone by
a human.

**Exit codes (`hotdocs verify`):**

| Code | Meaning |
| --- | --- |
| `0` | Ready — every item in scope has current, passing provenance. |
| `1` | Not ready — see `not_ready_reasons`. |
| `2` | Usage error. |

**Exit codes (`hotdocs track feedback`):**

| Code | Meaning |
| --- | --- |
| `0` | Ran (output may be empty if no failed attempt exists). |
| `2` | Usage error. |
