# Verification

Generated tests (`compiled`, `generated-test`, and `llm-judge` outputs),
contract/drift checks, and `corpus-graph.json` — the single generated
manifest the traceability matrix and the D9 graph/docs explorer both
render from.

See `SPEC_GUIDELINES.md` §6 (verification gates) and §7 (provenance).

## Seven real test suites, one per real component

Each directory below has its own `BOOTSTRAP.md` with the full, honest
account: what was ambiguous, what was decided, and — for every one of
them — at least one real bug a synthetic fixture or a real end-to-end
run caught that reading the code alone would have missed.

- `spec-linter/` — 42 tests. `criterion-compiler` doesn't exist to have
  compiled these the normal way.
- `graph-query-engine/` — 7 tests, run against this repo's own real
  corpus (not a synthetic fixture — these views exist specifically to
  query the real thing).
- `corpus-graph-builder/` — 8 tests. **Cold-generated, not hand-written**
  — the fixture suite here still had to be hand-authored, since
  `test-author` doesn't exist yet either.
- `llm-endpoint/` — 6 tests, all against an injected mock backend, zero
  cost to re-run. **Self-hosted twice over** (`D34`/`D35`) — this
  suite has been rewritten twice to match each regeneration's own,
  equally spec-conformant internal backend convention, since
  `interface/library.md` only ever fixes the public `complete()` call
  shape, never a Python return type.
- `cache-manager/` — 10 tests, including eight real concurrent writer
  threads that caught a genuine race condition no amount of reading the
  code would have found.
- `spec-bundle-assembler/` — 10 tests against a synthetic
  dependency-pair fixture, plus a direct smoke test against this repo's
  own real corpus.
- `generator/` — 10 tests, all against an injected mock backend. Used in
  anger twice: once to regenerate `llm-endpoint` (twice), once to
  attempt regenerating itself — the one real generation attempt this
  corpus has made that failed and was correctly rejected.

Run any one with `pytest` (not vendored into the repo — install into your
own environment) — but run every suite as its **own, separate** `pytest`
invocation, never two or more together in one command. Each directory's
bare-named `conftest.py` collides with any other's in Python's own
module cache the moment both are collected in the same run — a known,
accepted quirk of non-package test directories (confirmed directly:
every pairwise combination collides the same way), not a bug in any one
suite. See any `BOOTSTRAP.md` for the full note.

Everything else fills in as the corresponding components get real code.
