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
`read_yaml_frontmatter()`/`read_text()`/`UNNEST` calls, this document
names three views as the one shared surface all of them query. A
component MAY define additional views of its own for data no other
component needs (see `corpus-graph-builder` below) but MUST NOT redefine
these three.

**`nodes`** — one row per spec id in the corpus, across all four kinds.
Components, product capabilities, and vars come from their own
frontmatter; **guarantees carry no frontmatter at all** (D15 — unit-file
identity is the filename, not a `---` block), so a guarantee row is built
from `read_text()` and its filename alone, with `owner_component_id`
extracted from its path rather than read from any field:

```sql
CREATE VIEW nodes AS
SELECT id, title, status, 'component' AS kind, NULL AS owner_component_id
FROM read_yaml_frontmatter('specs/components/*/component.md', filename:=true)
UNION ALL
SELECT id, title, status, 'capability', NULL
FROM read_yaml_frontmatter('specs/product/*.md', filename:=true)
UNION ALL
SELECT id, title, status, 'var', NULL
FROM read_yaml_frontmatter('specs/vars/*.md', filename:=true)
UNION ALL
SELECT
  regexp_extract(filename, '(G-[A-Z0-9-]+)\.md$', 1), NULL, NULL, 'guarantee',
  'comp-' || regexp_extract(filename, 'specs/components/([^/]+)/interface/guarantees/', 1)
FROM read_text('specs/components/*/interface/guarantees/*.md', filename:=true);
```

This is the fix for a gap `R-IMPACT-009`'s original wording left open:
that wording named only the three frontmatter sources, with no mechanism
for enumerating guarantee nodes at all — meaning the target side of a
`depends_on_guarantees` edge was never actually resolvable against a real
node, only assumed to exist. `nodes` closes that gap, and
`owner_component_id` is what lets `spec-linter`'s R-LINT-018 check (below)
be a plain join instead of bespoke path-parsing.

**`edges`** — one row per `(source_id, target_id, edge_type)`, unnested
from each component's list-valued frontmatter fields:

```sql
CREATE VIEW edges AS
SELECT id AS source_id, UNNEST(depends_on) AS target_id, 'depends_on' AS edge_type
FROM read_yaml_frontmatter('specs/components/*/component.md')
UNION ALL
SELECT id, UNNEST(realizes), 'realizes'
FROM read_yaml_frontmatter('specs/components/*/component.md')
UNION ALL
SELECT id, UNNEST(uses_var), 'uses_var'
FROM read_yaml_frontmatter('specs/components/*/component.md')
UNION ALL
SELECT id, UNNEST(depends_on_guarantees), 'depends_on_guarantees'
FROM read_yaml_frontmatter('specs/components/*/component.md');
```

**`component_docs`** — one row per component, frontmatter fields joined
with the file's full raw text (frontmatter included), for anything that
needs structure and prose together rather than just the graph shape:

```sql
CREATE VIEW component_docs AS
SELECT fm.*, t.content AS body
FROM read_yaml_frontmatter('specs/components/*/component.md', filename:=true) fm
JOIN read_text('specs/components/*/component.md', filename:=true) t USING (filename);
```

`component_docs` is the data layer, not the rendered output — it answers
"what does this component's frontmatter and prose say," not "what should
a human see." Assembling an actual compiled, cross-linked document
(ordering sections, turning ids into hyperlinks) is still
`docs-site-renderer`'s job, the same way `merge-tracker-ui` renders
`merge-tracker`'s data rather than the data layer doing its own
presentation.

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
  are joins and aggregates against `nodes`/`edges` plus two views scoped
  to this component alone (`component_provenance`, `component_size` —
  see `R-GRAPH-009`), since no other component needs verification/
  provenance/size data joined onto the graph. Its JSON-writing role is
  unchanged (R-GRAPH-006/008: `verification/corpus-graph.json` is still a
  committed, deterministic artifact — only the *construction* step, not
  the output format, moves onto this engine).
- **`merge-orchestrator`'s `R-MERGE-014`** (golden-scenario gate) — "every
  product capability whose `realizes`-set intersects the blast radius" is
  now a single query against `edges` (`R-MERGE-020`), not a bespoke
  intersection written once for this call site.

**Not adopted, flagged as a distinct future candidate, not folded into
the above:** `spec-linter`'s requirement-traceability rules
(`rule_forward_traceability`/R-LINT-008, `rule_backward_traceability`/
R-LINT-009) walk a *different* graph — `R-id`/`AC-id` nodes (also
frontmatter-less unit files, same as guarantees) joined by each
acceptance file's `Covers:` tag, which is prose inside the file body, not
a list-valued frontmatter field. Modeling it would mean extending the
node/edge vocabulary this document defines (today: components,
capabilities, vars, guarantees) to cover requirement- and
acceptance-criterion-level ids too, which is a bigger scope change than
reusing the existing `nodes`/`edges` shape — worth its own decision later,
not assumed here.

## What this document does not cover

The merge-tracking data store (`merge-tracker`/`merge-tracker-ui`,
`P-MERGE-VISIBILITY`) also uses DuckDB, but as a query layer over
durable, append-only `TrackingRecord` JSON on local disk
(`.hotdocs/tracking/`), queried via core `read_json` — no `yaml` or
`duckpgq` extension, no spec-corpus frontmatter involved. That's a
different shape of problem (accumulating history across runs vs.
recomputing a snapshot fresh every run) with a different persistence
answer, specified in full in `specs/components/merge-tracker/` and
`specs/components/merge-tracker-ui/`, not here.

## Change log

- Initial draft.
