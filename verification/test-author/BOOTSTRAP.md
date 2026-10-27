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

## Round 2 (`D94`): nonce-delimited output protocol

The first real, non-mocked `author_test` call against a genuine
downstream criterion — bootstrapping `provenance-tracker`, the first of
the seven still-unbuilt components — surfaced a real gap invisible to
every `AC-AUTHOR-*` criterion's own mocked-backend verification: the
prompt said only "Output only the test code," with no reliable
extraction step on the receiving end. Against five real criteria, this
produced a markdown-fenced response once and four partial transcripts
of an attempted (and blocked) tool call the rest of the time, since
nothing told the model it has no tool or file access.

Fixed in the spec first (`R-AUTHOR-009`, `D94`): the same per-call
nonce-delimited BEGIN/END marker format `generator` already uses
(`D38`), plus an explicit no-tool-access instruction. One real
`generate()` call against the updated spec bundle produced a candidate
that correctly implements both — markers, strict between-marker
extraction (discarding any fence/narration outside them), and a
distinct `malformed_response` outcome (file `None`, nothing cached or
written to disk) when a response has no matching marker pair. Also
drops this component's own redundant `CriterionBundle` class in favor
of a bare duck-typed `bundle` parameter — not itself required by
`R-AUTHOR-009`, but a reasonable simplification consistent with the
corpus's general plain-value cross-component convention (the same
reasoning `R-TRACK-004` states for `provenance-tracker`), so the hand-
maintained `AC-AUTHOR-*` test suite's fixture now builds a
`SimpleNamespace` instead.

The hand-maintained `verification/test-author/test_test_author.py`
suite (the same mocked-backend verification exception `D58`'s bootstrap
already established for this component, since nothing else can verify
`test-author` without it already working) was updated: every mock
response now wraps its content in the real marker format via a shared
`file_block` conftest helper that reads the nonce back out of the
prompt actually sent, and two new cases cover `AC-AUTHOR-009` directly
(stripping a fence-and-narration wrapper around the markers; a
no-marker-pair response treated as a distinct failure with nothing
cached or written). All 10 test cases (the original 8 `AC-AUTHOR-*`
criteria plus 2 covering the new `AC-AUTHOR-009`) pass against the new
candidate. Swapped in; the pre-fix candidate is not kept.

## Round 3 (`D96`): dependency-resolution convention

`provenance-tracker`'s own re-verification against the round-2
candidate above still failed three of five `AC-TRACK-*` criteria, all
for the same underlying reason despite round 2's protocol fix working
correctly: nothing told the model that this corpus's components
resolve each other dynamically at runtime, never via a name Python's
own import system or `unittest.mock.patch` could find statically. One
authored test guessed a nonexistent package-submodule import path;
two assumed dependencies were patchable by name; the one that did
correctly reproduce the real dynamic-loading shape for the component
under test omitted the one correctness-critical `sys.modules`
pre-registration step — the same specific pitfall this corpus's own
real loaders (`generator`, `test-author` itself, `provenance-tracker`)
already had to learn the hard way once each.

Fixed in the spec (`R-AUTHOR-010`, `D96`): a fixed, always-included
instruction stating the convention plus a literal worked snippet
(prose alone already proved insufficient once). One real `generate()`
call against the updated spec bundle produced a candidate whose prompt
correctly includes the full convention text and worked snippet,
verbatim, via a module-level `DEPENDENCY_CONVENTION_INSTRUCTION`
constant. `PROMPT_VERSION` → `v3`; `file`/`model_call_error` are now
plain dicts again (this round's own reasonable representation choice,
not itself required by any requirement). The hand-maintained
`AC-AUTHOR-*` suite was updated for the dict shape and gained
`AC-AUTHOR-010`, asserting the convention text, path pattern, and
correct snippet ordering all appear in the real prompt sent. All 11
test cases pass against the new candidate. Swapped in; round 2's
candidate is not kept.
