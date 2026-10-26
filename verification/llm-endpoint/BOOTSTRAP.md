# Bootstrap Account: `llm-endpoint`

A fourth hand-authored bootstrap exception, same honest flag
`spec-linter`/`graph-query-engine`/`corpus-graph-builder`'s own
`BOOTSTRAP.md` accounts already establish — but a structurally different
reason this time. The other three are bootstrap exceptions because no
real `generator` exists yet to have produced them the normal way.
`llm-endpoint` can never be produced the normal way at all, even once a
real `generator` exists: `generator` would dispatch through
`llm-endpoint` to do the generating, so nothing could ever have
generated `llm-endpoint` first. This is a permanent structural fact
about this component, not a temporary gap closed once tooling catches
up — worth naming precisely rather than filing under the same "not
built yet" bucket as the other three.

**Real backend, confirmed live exactly once, not on every test run.**
`AnthropicBackend` shells out to the `claude` CLI's non-interactive
mode (`D45`/`D46`), which bills real money per call now that
`ANTHROPIC_API_KEY` is set in this environment (`D46`). One real call
was made to confirm the integration actually works end to end:

```
complete("Reply with exactly the word: PONG", "claude-sonnet-5")
-> text="PONG", model="claude-sonnet-5", backend="anthropic", model_call_error=None
```

— and its `.hotdocs/calls/` record was independently confirmed queryable
via DuckDB's `read_json`, per `R-ENDPOINT-006`/`AC-ENDPOINT-006`'s own
framing. This is the only real network call this component's bootstrap
made. Every other verification uses an injected mock backend
(`interface/library.md`'s `backend` parameter, `D47`) — exactly what
`AC-ENDPOINT-002`/`003`/`006` already specify, not a workaround invented
here. The full `verification/llm-endpoint/` suite costs nothing to
re-run, by design.

**`model_call_error.category` classification is a best-effort heuristic,
not independently verified against real auth/network/rate-limit
failures** — doing so would mean deliberately triggering real billed
failures (a bad credential, an actual rate limit) for no verification
benefit a mock doesn't already provide more cheaply. The `claude` CLI's
JSON result carries a real `api_error_status` field (confirmed present,
`null` on success, in the one live call above) that maps cleanly to
`auth`/`rate_limit`/`timeout`; stderr text-matching is only a fallback
for failures that status code doesn't cover (e.g. the CLI itself not
found on `PATH`). If this mapping turns out wrong against a real failure
someday, that is a real bug to fix then, not a risk accepted silently —
flagged here so it isn't mistaken for already-verified.

**`AC-ENDPOINT-005`'s own Gherkin ("dispatches successfully") was
interpreted as testing internal model-to-backend resolution, not a real
network round-trip** — it's `kind: compiled` (deterministic, no
model/judgment involved), and a routine test suite making a real,
billed network call on every run would contradict that `kind` and this
component's own `constraints.md` ("idempotent dispatch is not claimed").
Tested directly against `_resolve_backend("claude-sonnet-5")` instead,
confirming it returns a real `AnthropicBackend` instance without
raising and without needing `backend=` injected.

**`interface/library.md` gained a `backend` parameter** (`D47`) that
wasn't in the original spec — the same kind of pre-existing gap
`provenance-writer`'s `ProvenanceInputs` and `generator`'s
`GenerationResult` each had before being noticed and fixed. Every one
of `R-ENDPOINT-001`'s own acceptance criteria already required an
"injected mock backend," so the interface was always going to need
this; it just hadn't been written down yet.
