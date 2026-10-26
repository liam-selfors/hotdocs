# Bootstrap Account: `cache-manager`

Fifth hand-authored bootstrap exception — but, unlike `llm-endpoint`,
a temporary one: nothing stops a real `generator` from cold-regenerating
this component later, now that a real `generator`/`llm-endpoint` pair
could exist.

**v1 implements only the local `.hotdocs/cache/` fallback**
(`R-CACHE-009`) — `VAR-CACHE-STORE-URL`, when set, is treated the same
as any other unreachable backing store (`R-CACHE-004`'s fail-to-miss),
since no real shared-store client exists in this project to target yet
(D18/D20).

**One real concurrency bug found by actually running concurrent writers**,
not by reading the code: the atomic-write temp filename was keyed by
`os.getpid()` alone, so concurrent *threads* in one process (which share
a pid) raced on the same temp path — `os.replace` raised
`FileNotFoundError` once a sibling thread's replace had already consumed
it. Fixed by keying the temp filename with a per-call `uuid4`, not just
the pid. Caught by `AC-CACHE-003`'s own test, run for real with eight
concurrent writer threads, not asserted from reading the code alone.

**`R-CACHE-006`'s `stats()` reports the local store's current entry
count only** — no persistent cumulative hit/miss counter is defined
anywhere in this component's own spec, so a richer "hit rate over time"
metric (`notes/metrics.md`) is not yet implemented; flagged here, not
silently claimed complete.

**`repo_root` added to `get`/`put`** (`D48`) — the same pre-existing-gap
pattern `llm-endpoint`'s `backend` parameter and `provenance-writer`'s
`ProvenanceInputs` each already were; `interface/cli.md`'s own
`--repo-root` flag implied it all along.

Verified: 10/10 tests pass (one per `AC-CACHE-*` criterion), all
deterministic, no model calls, no real network — matching this
component's own `constraints.md`.
