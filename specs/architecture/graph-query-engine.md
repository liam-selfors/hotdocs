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

## Query surface

Rather than let every adopting component write its own
`read_yaml_frontmatter()`/`read_text()`/`read_json()`/`UNNEST` calls,
seven shared views are the one surface all of them query — `nodes`,
`edges`, `component_docs`, `component_context`, `component_provenance`,
`component_size`, `decision_lineage` (`D74`). Their exact definitions,
generated SQL, and data contracts now live in their own component,
`specs/components/graph-query-engine/` (`D13`) — this document keeps
the adoption history below, not a second copy of the SQL.

Two of the six were promoted here from a single component's own
private definition, by the same rule each time: `component_provenance`
originally lived only in `corpus-graph-builder`'s spec (`R-GRAPH-009`)
until `review-packet-builder` (`R-PACKET-011`, D13) needed the exact
same manifest fields; `component_size` lived there too until
`spec-linter` (`D13`) needed the same word count `rule_size_caps` had
been computing independently. A component MAY define additional views
of its own for data no other component needs, but MUST NOT redefine
these six — a second real consumer is the signal to promote a local
view here, not leave two components maintaining their own copies.

None of these six had ever actually been run before `D13` found
and fixed three real bugs across them — `read_text`'s nonexistent
`filename:=true` parameter (present in four of `nodes`'s seven
branches, two of `edges`'s six, and `component_docs`), a missing
DOTALL flag in `component_context`, and `trim()`'s space-only
whitespace handling in `component_size`. All three were found by
running the SQL against real DuckDB and checking results against
independent counts, not by reading the written text — see
`graph-query-engine`'s own `BOOTSTRAP.md` for the full account.

## Scope of adoption

`impact-analyzer`'s blast-radius computation was the first component
rebuilt on this engine (see its own spec, `R-IMPACT-009` — now phrased in
terms of `nodes`/`edges` rather than restating the raw calls inline).
Adopted here as well, each via its own implementation-requirement
pointing back to this document, exactly as `R-IMPACT-009` does:

- **`spec-linter`'s graph-shaped reference-and-cycle rules** —
  `rule_reference_resolution` (R-LINT-003), `rule_acyclic_graph`
  (R-LINT-004), and `rule_depends_on_guarantees_resolution` (R-LINT-018)
  are queries over `nodes`/`edges` (`R-LINT-020`). This closes the same
  sequencing argument named in an earlier draft of this section:
  `spec-linter` validates this graph is well-formed *before*
  `impact-analyzer` trusts it (R-IMPACT-007), so sharing the construction
  step is more than tidiness — a single ingestion bug now surfaces in both
  places identically, instead of two independently-written parsers
  silently disagreeing about what the graph even is.
- **`corpus-graph-builder`** (`R-GRAPH-009`) — its structural graph
  (R-GRAPH-001/002) is `nodes`/`edges` directly; its per-node annotations
  (R-GRAPH-003: verification status, provenance summary, size-vs-cap
  status, sealed/override) and corpus-wide orphan rates (R-GRAPH-004/005)
  are joins and aggregates against `nodes`/`edges`/`component_provenance`/
  `component_size` — all four now shared here, none scoped to this
  component alone (`D13` promoted the last one). Its JSON-writing role
  is unchanged (R-GRAPH-006/008: `verification/corpus-graph.json` is
  still a committed, deterministic artifact — only the *construction*
  step, not the output format, moves onto this engine).
- **`spec-linter`'s size-cap rule** (`rule_size_caps`/`R-LINT-012`,
  `D13`) — `component_doc_words` is this view's `word_count`, queried
  directly rather than recomputed by a second, independently-written
  Python loop. The one adopter that actually runs a query against this
  engine via a real `duckdb` dependency, rather than reimplementing
  equivalent logic natively in Python the way `R-LINT-003`/`004`/`008`/
  `009`/`018`'s bootstrap implementation still does today (flagged in
  `notes/backlog.md`, not yet resolved).
- **`capability-scenario-verifier`'s capability-intersection lookup**
  (`R-SCENARIO-002`) — "every product capability whose `realizes`-set
  intersects the blast radius" is a single query against `edges`, not a
  bespoke intersection written once for this call site. This logic
  originally lived in `merge-orchestrator` as `R-MERGE-020`; it moved
  with the rest of the capability-scenario gate when D14 extracted
  `capability-scenario-verifier` (named `golden-scenario-verifier` at
  the time; renamed by `D23`) out of `merge-orchestrator` to relieve
  that component's fan-out/word-count caps.
- **`review-packet-builder`** (`R-PACKET-011`) — every field it reports
  from `verifier-orchestrator`/`license-scanner`/`secret-scanner` is
  read via `component_provenance` instead of a live call into any of
  them, since `provenance-writer` (which it already depended on)
  already collected all of it. Dropped its `depends_on`
  from 5 to 1 (D13).
- **`spec-linter`'s requirement-traceability rules**
  (`rule_forward_traceability`/R-LINT-008, `rule_backward_traceability`/
  R-LINT-009, `R-LINT-021`, D13) — originally flagged below as a
  distinct, deferred candidate because it appeared to need a second graph
  vocabulary (`R-id`/`AC-id`/`GS-id` nodes — `GS-id` renamed `CS-id` by
  `D23`). Reading `spec_linter.py`'s actual implementation showed the
  real need is smaller: R-LINT-008 only counts `covers`-edges per
  requirement, R-LINT-009 only validates each edge's *target* against
  `nodes` — neither needs `AC-id`/`CS-id` as addressable nodes for its
  own check to work. D13 adopted the fuller
  shape anyway (`requirement`/`acceptance`/`capability_scenario` all modeled
  as proper `nodes`, not just the minimum each rule strictly needs), for
  a complete graph rather than one trimmed to today's two consumers.
- **`spec-bundle-assembler`** (`R-ASSEMBLE-010`, `D22`) — each
  dependency's `Purpose` text, handed to a dependent as
  `dependency_context`, is read via `component_context` rather than
  reaching into the dependency's `component.md` directly. A narrow,
  explicit exception to `R-ASSEMBLE-002`'s otherwise-correct "never
  `component.md`" rule, scoped to exactly the one section `D21` made
  dependent-safe by construction.

## What this document does not cover

`P-MERGE-VISIBILITY`'s own component, `provenance-tracker-ui` (formerly
`merge-tracker-ui`, `D88`), does not use DuckDB at all since `D154`: it
calls `provenance-tracker`'s `check_readiness` in Python and reads
`corpus-graph.json` and `.hotdocs/attempts/` as plain JSON at build
time, specified in full in `specs/components/provenance-tracker-ui/`,
not here.

## Change log

- Initial draft.
