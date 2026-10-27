# CLI

```
hotdocs verify [--changed=<spec-id>...] [--model=<model-id>] [--seed=<n>] \
  [--repo-root=<dir>] [--format=json|text]
hotdocs track feedback <component-id> [--repo-root=<dir>]
```

`hotdocs verify` (`R-TRACK-009`/`010`, `D88`/`D93`) is the canonical
"will a merge pass" command — omitting `--changed` checks the whole
corpus, supplying it checks just that blast radius. Every component in
scope is only ever checked against `provenance-checker`, read-only —
this command never triggers `component-gate-runner` (`D93`); every
intersecting capability is checked-then-run against
`capability-scenario-verifier` (`D89`/`D92`, unreversed by `D93`),
since that never produces new source code. `--model` is required only
when some capability in scope actually needs a fresh run; a scope
that's already fully current never needs it — supplying it when
nothing needs it is harmless. Exit `0` means `ready` is `true`; exit
`1` means at least one component or capability in scope is not ready,
with `not_ready_reasons` printed (`--format=text`, the default) or
available as structured data (`--format=json`). This command confirms
readiness; it does not gate anything itself — nothing requires it to
be run before a commit (`D87`).

`track feedback` (`R-TRACK-008`, `D3`) prints the named component's
most recent failing `R-id`s, comma-separated, ready to paste into
`hotdocs generate <component-id> --retry-feedback=...` (`D86`/`D93`) —
or nothing, if no failed attempt exists. It does not pass anything
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
| `2` | Usage error (e.g. a capability in scope needs a fresh run and `--model` was not supplied). |

**Exit codes (`hotdocs track feedback`):**

| Code | Meaning |
| --- | --- |
| `0` | Ran (output may be empty if no failed attempt exists). |
| `2` | Usage error. |
