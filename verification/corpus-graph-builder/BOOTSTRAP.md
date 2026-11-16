# Bootstrap Account: `corpus-graph-builder`

Different from `spec-linter`'s and `graph-query-engine`'s own
`BOOTSTRAP.md` accounts: `gen/corpus-graph-builder/` was **not**
hand-written. It was produced by a real model call — the `generator`
Claude Code subagent (`.claude/agents/generator.md`), standing in for
`comp-generator` dispatching through `comp-llm-endpoint`, because
neither of those exist yet. The subagent was given exactly this
component's assembled `SpecBundle` (`spec`/`interface`/`constraints`/
`dependency_interfaces`/`dependency_context`/`vars`/`glossary` — never
`acceptance/`, never any other component's real `gen/` code) and nothing
else, matching `R-GEN-001`'s cold-mode purity rule for the real thing.

**Verified two ways, neither by just "did it run":**

1. Against this repo's real corpus: node count (30), edge count (86),
   and all three orphan rates (`0.0`, `0.0`, `0.0`) were each
   cross-checked against an independent count computed a different way
   (`pathlib`/`re` over the real file tree, not DuckDB) — exact match
   on every one.
2. Against a synthetic fixture (`conftest.py`), because this repo's own
   corpus currently has zero orphans of any kind and several
   `AC-GRAPH-*` criteria specifically require one as their "Given" —
   the same reason `spec-linter`'s own test suite uses a synthetic
   corpus rather than this repo's real one.

**One real bug found only once a real `.provenance.json` existed to
query:** `component_provenance`'s `generated_at` field auto-detects as
`TIMESTAMP WITH TIME ZONE`, and materializing that type requires `pytz`
— not installed, since nothing had ever read a real provenance manifest
through this view before. Not a bug in the generated code itself (it
correctly used the shared view as required, R-GRAPH-009) — a transitive
dependency gap in `graph-query-engine` invisible until exercised with
real data. Fixed by declaring `pytz` as a real dependency
(`gen/corpus-graph-builder/pyproject.toml`); see `R-GQE-005` and
`graph-query-engine`'s own `BOOTSTRAP.md` for the full account.

**Determinism (R-GRAPH-008) confirmed by hand:** `build_corpus_graph`
run twice against the same repo state produces byte-identical
`to_json_bytes()` output.

**One structural choice worth naming, not silently normalized away:**
the generated code is a `corpus_graph_builder/` package (with its own
`pyproject.toml`) rather than the flat single-file style
`spec-linter`/`graph-query-engine` use. Nothing in `interface/library.md`
or any requirement mandates a flat layout — this was the model's own
reasonable structural choice given only the spec, not an error, and
tells its own small story about what "cold, with no prior code" actually
produces when no file-layout convention is stated.

**Not tested here:** `AC-GRAPH-007` ("runs on every merge to main") is a
CI-cadence requirement, not a property `build_corpus_graph()` itself can
satisfy or fail — no real CI pipeline exists in this repo to test
against.
