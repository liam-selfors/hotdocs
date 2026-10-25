---
id: arch-graph-query-engine
title: Graph Query Engine
status: draft
owners: [pipeline-team]
depends_on: []
---

# Graph Query Engine

## Purpose

The corpus's dependency structure (`depends_on`, `realizes`, `uses_var`,
`depends_on_guarantees` — the same edges `impact-analyzer`'s blast-radius
computation and `spec-linter`'s traceability rules each independently walk
today) is a property graph: nodes are spec ids (components, product
capabilities, vars, guarantees), edges are typed relationships between
them. This document names the engine components querying that graph
should use, so the choice is made once, in one place, rather than
separately per component — the same reason `step-phrase-grammar.md` lives
here rather than inside one component's own `interface/`.

**DuckDB**, embedded and local (no server process, no network dependency —
consistent with every other component's "no network access" posture),
queried via two extensions:

- **`yaml`** (DuckDB community extension) — specifically its
  `read_yaml_frontmatter()` function, which extracts the YAML block
  between `---` delimiters at a file's start and returns one row per
  file, frontmatter fields as columns, with native glob support
  (`read_yaml_frontmatter('specs/components/*/component.md',
  filename:=true)`). This is what lets a component query frontmatter
  **directly out of the existing spec files** — `component.md`, `specs/
  product/*.md`, `specs/vars/*.md`, all of which already carry this exact
  frontmatter convention — with no file restructuring, no new committed
  artifact, and no change to `SPEC_GUIDELINES.md`'s layout. A prior
  version of this decision considered splitting frontmatter into a
  dedicated per-component file specifically to make it queryable; that
  turned out to be solving a problem `read_yaml_frontmatter()` already
  doesn't have.
- **`duckpgq`** (DuckDB community extension) — SQL/PGQ pattern-matching
  (`MATCH` syntax) for graph-shaped traversal: transitive reachability,
  cycle detection, blast-radius-style queries. Chosen over hand-rolled
  recursive SQL CTEs for the same reason `criterion-compiler` exists
  instead of asking a model to interpret Gherkin afresh each time —
  expressing a well-defined operation in its own dedicated grammar beats
  reimplementing it in a more general-purpose one.

## Verified compatibility (checked directly, not assumed)

Both extensions' DuckDB-WASM support was confirmed against their actual
compatibility matrices (not the markdown-converted summary of those pages,
which silently drops the SVG check-mark icons and reads as "unsupported"
when it isn't — a mistake made and caught during this decision's own
research, worth recording so it isn't repeated):

- **`yaml`**: full support (every platform including WebAssembly) across
  every currently-listed DuckDB version (1.4.4 through 2.0.0). The only
  unsupported platform is Windows ARM64, irrelevant here. Small extension
  (~20 GitHub stars, 2 open issues at time of writing) with active, recent
  commits, MIT-licensed, built on DuckDB's official extension template.
  Its own documentation discloses it was written primarily with AI
  assistance — a real provenance difference from a long-established
  library, not disqualifying given the compatibility matrix and the low
  cost of the fallback below, but worth naming rather than glossing over.
- **`duckpgq`**: WebAssembly (and every other platform) supported on
  1.4.4, 1.5.6, and 2.0.0; unsupported on 1.4.5 and 1.5.5 specifically
  (a gap affecting *every* platform equally for those two patch releases,
  not a WASM-specific shortfall). A CWI research-group extension with
  substantially wider adoption (~21.7k weekly downloads at time of
  writing) than `yaml`.

**Fallback posture, if either extension becomes unavailable or
unreliable:** this is a swap of the ingestion/query step only, not a
redesign. Frontmatter parsing already exists, independently, in
`spec-linter`'s own implementation (`_parse_frontmatter`) — that logic
could feed DuckDB tables via its Python API (registering an in-memory
list of dicts or a DataFrame as a queryable relation) instead of via
`read_yaml_frontmatter()`, with no change to anything consuming the
resulting graph. Graph traversal without `duckpgq` would fall back to
recursive CTEs — more verbose, not infeasible.

## Scope of adoption

`impact-analyzer`'s blast-radius computation is the first component
rebuilt on this engine (see its own spec). Not adopted here, flagged as
candidates for the same realignment in a later, separate decision:

- **`spec-linter`'s graph-shaped rules** — cycle detection
  (`rule_acyclic_graph`), forward/backward traceability
  (`rule_forward_traceability`/`rule_backward_traceability`), and
  reference resolution (`rule_reference_resolution`,
  `rule_depends_on_guarantees_resolution`) are, structurally, queries over
  the same graph `impact-analyzer` now builds. The strongest candidate,
  partly because `spec-linter` already has to validate this graph is
  well-formed *before* `impact-analyzer` trusts it (R-IMPACT-007) — a
  genuine sequencing argument for sharing the construction step, not just
  a tidiness one.
- **`corpus-graph-builder`** — builds the same underlying structural graph,
  post-merge, with verification-status and provenance annotations joined
  on top, for `docs-site-renderer` to consume later. Its JSON-writing role
  stays necessary regardless (a browser-based, detached consumer needs an
  actual file to fetch) — only the graph-*construction* step is a
  realignment candidate, not its output format.
- **`merge-orchestrator`'s `R-MERGE-014`** (golden-scenario gate) — "every
  product capability whose `realizes`-set intersects the blast radius" is
  a smaller graph lookup that could query the same representation.

## What this document does not cover

A separate, not-yet-speced initiative — a merge-tracking data store
(per-merge-attempt, per-component generation/verification history,
queryable for metrics and a future UI) — also plans to use DuckDB, but as
a query layer over durable, append-only JSON event records on disk, not
over the spec corpus's frontmatter. That's a different shape of problem
(accumulating history across runs vs. recomputing a snapshot fresh every
run) with a different answer about what gets persisted, and is tracked
separately, not specified by this document.

## Change log

- Initial draft.
