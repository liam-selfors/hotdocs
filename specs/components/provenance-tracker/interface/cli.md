# CLI

```
hotdocs verify [--changed=<spec-id>...] [--model=<model-id>] [--seed=<n>] \
  [--repo-root=<dir>] [--format=json|text]
hotdocs track feedback <component-id> [--repo-root=<dir>]
```

`main(argv)` receives `argv` beginning `["verify", ...]` or `["track",
"feedback", ...]`; every flag takes its value as `--flag=value` or as the
next argument, and `--changed` may repeat. `main` calls `check_readiness`
and `last_requirement_failures` through this module's own global names,
so a test may replace them.

`hotdocs verify` (`R-TRACK-009`/`010`, `D88`/`D93`) answers "will a merge
pass": without `--changed` it checks the whole corpus, with it that blast
radius. Components are only checked against `provenance-checker`,
read-only, never triggering `component-gate-runner` (`D93`); intersecting
capabilities are checked-then-run against `capability-scenario-verifier`
(`D89`/`D92`). `--model` is needed only when a capability needs a fresh
run. `--format=text` (default) prints `ready` or `not ready` and then each
`not_ready_reasons` entry on its own line; `--format=json` prints the
result as JSON, converted as `R-TRACK-007` converts its inputs. Nothing requires running it before a commit (`D87`).

`track feedback` (`R-TRACK-008`, `D3`) prints the named component's most
recent failing `R-id`s, comma-separated, ready for `hotdocs generate
<component-id> --retry-feedback=...` (`D86`/`D93`), or nothing if no
failed attempt exists.

There is no `hotdocs track write`: `component-gate-runner` calls
`write_attempt_record` directly.

**Exit codes (`hotdocs verify`):**

| Code | Meaning |
| --- | --- |
| `0` | Ready — every item in scope has current, passing provenance. |
| `1` | Not ready — see `not_ready_reasons`. |
| `2` | Usage error: an unknown argument, a non-integer `--seed`, an invalid `--format`, a flag given last with no value, or a capability in scope that needs a fresh run without `--model`. |

**Exit codes (`hotdocs track feedback`):**

| Code | Meaning |
| --- | --- |
| `0` | Ran (output may be empty if no failed attempt exists). |
| `2` | Usage error: no `<component-id>`, an unknown argument, or a first word other than `verify` or `track feedback`. |

Every usage error, for either command, prints one line naming its cause
to stderr before exiting `2`, never a traceback.
