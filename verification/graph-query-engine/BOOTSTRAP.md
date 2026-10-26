# Bootstrap Account: `graph-query-engine`

The same honest exception `spec-linter`'s own `BOOTSTRAP.md` already
documents, a second time: `gen/graph-query-engine/` was built by hand,
standing in for `generator` (no cold-regen pipeline exists to have
produced it the normal way). Not a new pattern — flagged explicitly,
same as the first time.

**One real bug found only by running this against the real corpus, not
by reading the spec:** `component_provenance`'s `read_json` call raises
when its glob matches zero files, and this repo — having no real
`generator` — has never actually produced a single real
`.provenance.json`. The view as first implemented would have failed on
every single invocation in this repo's own current state, not just in
some hypothetical edge case. `R-GQE-005` was amended to require an
explicitly-typed empty fallback once this was found; see
`gen/graph-query-engine/graph_query_engine.py`'s
`_EMPTY_COMPONENT_PROVENANCE`.

**One bug in the loader itself, not the SQL:** the first cut of
`load_views`'s statement-splitting skipped any statement whose
*first line* was a comment, intending to filter out empty/comment-only
statements — but the `nodes` view's own `CREATE VIEW` statement
followed a leading comment block in the same file, so the whole
statement (comment *and* the real SQL after it) was silently skipped,
and `nodes` was never created at all. Caught immediately by actually
querying the view afterward, not by the loader call itself succeeding
without error — `load_views` not raising is not the same thing as
`load_views` having done what was asked.

**Every view's row/edge counts were cross-checked against an
independent count computed a different way** (`pathlib`/`re` over the
real file tree, not DuckDB) — not just "did the query run without
error." This is the same discipline `D42`/`D43` already established:
running SQL and getting a result back is not the same as the result
being correct.
