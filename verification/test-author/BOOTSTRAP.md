# Bootstrap Account: `test-author`

First real cold-generation of this component, via the self-hosted
`gen/generator/generator.py` (`D58`), through two real spec fixes and
four `generate()` calls (one a deliberate plain retry, forced past a
legitimate cache hit).

**Call 1** set `GATE_VERSION = "test_author@v1"`, reasonably mirroring
`generator`'s own pattern where the `gate_version` prefix equals the
component's own name — but `cache-manager`'s six-entry `gate_type`
registry has no `test_author` entry; the real one for this kind of
artifact is `generated_test`. Crashed on its own first cache write.
Fixed by clarifying `R-AUTHOR-004` explicitly (`D72`). Not swapped in.

**Call 2**, with that fix in place, implemented exactly
`interface/library.md`'s then-documented signature —
`author_test(bundle, model, seed=0)` — which never declared an
injectable backend at all, despite every `AC-AUTHOR-*` criterion's own
Gherkin requiring "a mock model." A genuine interface gap, not a
candidate mistake: `generator`'s own `library.md` already documents an
`llm_backend` parameter for exactly this reason; `test-author`'s never
did. Fixed by adding it explicitly, mirroring `generator`'s parameter
name (`D73`). Not swapped in.

**Call 3**, with both fixes in place, correctly added `llm_backend`
and the right `gate_version` — but its dependency loader's
flat-module fallback checked `gen/<slug>.py` (a sibling of `gen/`
itself) instead of `gen/<slug>/<module>.py`, an asymmetric bug: the
*package*-loading branch right above it checked the correct nested
path. A plain implementation defect, not a spec gap. Deleted, not
swapped in.

**Call 4** (a plain retry) returned the *same* call-3 candidate from
cache — correctly, since nothing about the component's own `SpecBundle`
had changed between attempts and the cache key doesn't know a human
rejected the cached result for a reason outside the key. Forced a
genuinely fresh call by deleting that one specific stale cache entry
directly, confirmed first by inspecting its payload. The resulting
candidate correctly nests the flat-module path. Verified against all
8 `AC-AUTHOR-*` criteria for real. Swapped in.

One operational hazard found and fixed during the swap itself: an
earlier `rm -rf gen/test-author` + a cache-hit replay before the
final fix left a stale `test_author/` *package* directory sitting
alongside the final flat `test_author.py` module — Python's import
machinery silently preferred the stale package, making tests run
against rejected code without erroring. Caught by a failing traceback
that still named the old (rejected) module's internal structure.
Fixed by removing the whole `gen/test-author/` directory and
recreating it with only the final candidate's one file.
