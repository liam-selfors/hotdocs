# Bootstrap Account: `llm-endpoint`

**Superseded twice by real self-hosted regeneration.** The current
`gen/llm-endpoint/llm_endpoint.py` is the
*second* generated version — produced after `R-ENDPOINT-004` gained a
concrete 300-second timeout floor (`D34`) and `R-ENDPOINT-003` gained a
structural `--tools ""`/`--bare` isolation requirement (`D35`, found by
a real contamination: an earlier regeneration attempt, dispatched
without a properly-forwarded system prompt, used tool access to inspect
this actual repository's live git state instead of treating its prompt
as an isolated completion). Both fixes show up directly in this
version's own code and comments — confirmed by reading it, not assumed.
This is now a *third* distinct internal convention for `complete()`'s
return shape across three generations (an object with `.to_dict()`,
the original hand-authored bootstrap; a bare `(text, error)` tuple,
the first self-hosted regeneration; a plain dict, the second) — every
one spec-conformant, since `interface/library.md` only ever fixed the
public `complete(prompt, model, *, backend=None, **params)` signature,
never a Python return type. `generator.py` (`gen/generator/generator.py`)
was given a small `_as_dict()` adapter so it depends on the JSON
contract rather than whichever shape the currently-installed
`llm-endpoint` happens to return — the real, recurring cost of this
kind of self-replacement, paid once properly rather than re-patched
ad hoc on every future swap. See `D34`/`D35` for the full account.

---

**Superseded by a real self-hosted regeneration.** Everything
below this notice describes the original hand-written bootstrap —
kept as the historical record, since the discovery process
and bugs it documents are still real and still relevant. `gen/llm-endpoint/`
is no longer that hand-written file: it is the
output of a genuine `generate()` call (the real `generator`,
dispatching through the very `llm-endpoint` it was about to replace)
against this component's own current spec, verified against every
`AC-ENDPOINT-*` criterion and swapped in because it passed. See this
component's own decision history for the full account, including the
one real behavioral difference the swap introduced: the self-hosted version's
backend-injection shape is a plain callable, not the original's
`.complete()`-method object — `verification/llm-endpoint/`'s own test
suite was updated to match, since that shape was never part of the
public interface spec, only an internal choice each version is free to
make independently.

---

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
mode (`D33`), which bills real money per call now that
`ANTHROPIC_API_KEY` is set in this environment (`D32`). One real call
was made to confirm the integration actually works end to end:

```
complete("Reply with exactly the word: PONG", "claude-sonnet-5")
-> text="PONG", model="claude-sonnet-5", backend="anthropic", model_call_error=None
```

— and its `.hotdocs/calls/` record was independently confirmed queryable
via DuckDB's `read_json`, per `R-ENDPOINT-006`/`AC-ENDPOINT-006`'s own
framing. This is the only real network call this component's bootstrap
made. Every other verification uses an injected mock backend
(`interface/library.md`'s `backend` parameter, `D33`) — exactly what
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

**`interface/library.md` gained a `backend` parameter** (`D33`) that
wasn't in the original spec — the same kind of pre-existing gap
`provenance-writer`'s `ProvenanceInputs` and `generator`'s
`GenerationResult` each had before being noticed and fixed. Every one
of `R-ENDPOINT-001`'s own acceptance criteria already required an
"injected mock backend," so the interface was always going to need
this; it just hadn't been written down yet.
