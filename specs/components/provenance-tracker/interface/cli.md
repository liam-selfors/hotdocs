# CLI

```
hotdocs build [<component-id>] --model=<model-id> [--seed=<n>] \
  [--changed=<spec-id>...] [--retry-feedback=<R-id>,...] \
  [--repo-root=<dir>] [--format=json|text]
hotdocs track feedback <component-id> [--repo-root=<dir>]
```

`hotdocs build` (`R-TRACK-009`/`010`, `D92`) replaces `hotdocs generate`,
`hotdocs check-capability`, and `hotdocs verify` entirely — the one
command a developer runs. `--model` is required whenever this scope
contains anything not already passing — no implicit default, same
posture `generator`'s own former CLI held; a scope that turns out to
be fully passing already never needs it, but it MUST still be supplied
up front, since whether it will be needed isn't known until the checks
run. A bare `<component-id>` is shorthand for `--changed=<component-id>`
(a blast radius of exactly that component and its dependents);
omitting both checks the whole corpus. `--retry-feedback` is only
valid when exactly one component is in scope (a bare `<component-id>`,
or `--changed` naming exactly one) — a usage error otherwise. Exit `0` means `ready` is `true`; exit `1`
means at least one component or capability in scope is not ready, with
`not_ready_reasons` printed (`--format=text`, the default) or available
as structured data (`--format=json`). Nothing requires this command to
be run before a commit (`D87`) — it confirms and builds toward
readiness, it does not gate anything itself.

`track feedback` (`R-TRACK-008`, `D3`) prints the named component's
most recent failing `R-id`s, comma-separated, ready to paste into
`hotdocs build <component-id> --retry-feedback=...` (`D92`) — or
nothing, if no failed attempt exists. It does not pass anything
anywhere itself; it only answers "what would I pass," leaving whether
to pass it to the developer running the command.

There is no `hotdocs track write` CLI command — `AttemptRecord`s are
written by `component-gate-runner` directly (`R-GATE-008`), never run
standalone by a human, and never by this component either (`D92`).

**Exit codes (`hotdocs build`):**

| Code | Meaning |
| --- | --- |
| `0` | Ready — every item in scope has current, passing provenance. |
| `1` | Not ready — see `not_ready_reasons`. |
| `2` | Usage error (e.g. `--retry-feedback` with more than one component in scope). |

**Exit codes (`hotdocs track feedback`):**

| Code | Meaning |
| --- | --- |
| `0` | Ran (output may be empty if no failed attempt exists). |
| `2` | Usage error. |
