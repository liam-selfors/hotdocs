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
this document names four views as the one shared surface all of them
query. A component MAY define additional views of its own for data no
other component needs (see `corpus-graph-builder`'s `component_size`
below) but MUST NOT redefine these four — and if a second component ever
needs one of its own local views, that is the signal to promote it here
instead, same as `component_provenance`'s own history.

**`nodes`** — one row per spec id in the corpus, across seven kinds.
Components, product capabilities, and vars come from their own
frontmatter; **guarantees, requirements, and acceptance criteria carry no
frontmatter at all** (D15 — unit-file identity is the filename, not a
`---` block), so those rows are built from `read_text()` and filenames
alone, with `owner_component_id` extracted from path rather than read
from any field. **Golden scenarios are the one kind with no file of
their own** — they're `### GS-...` headings inside a product
capability's single file (`SPEC_GUIDELINES.md` §5), so their rows come
from extracting headings out of that file's body text, not from a glob
at all:

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
  regexp_extract(filename, '(G-[A-Za-z0-9-]+)\.md$', 1), NULL, NULL, 'guarantee',
  'comp-' || regexp_extract(filename, 'specs/components/([^/]+)/interface/guarantees/', 1)
FROM read_text('specs/components/*/interface/guarantees/*.md', filename:=true)
UNION ALL
SELECT
  regexp_extract(filename, '(R-[A-Za-z0-9-]+)\.md$', 1), NULL, NULL, 'requirement',
  'comp-' || regexp_extract(filename, 'specs/components/([^/]+)/requirements/', 1)
FROM read_text('specs/components/*/requirements/*.md', filename:=true)
UNION ALL
SELECT
  regexp_extract(filename, '(AC-[A-Za-z0-9-]+)\.md$', 1), NULL, NULL, 'acceptance',
  'comp-' || regexp_extract(filename, 'specs/components/([^/]+)/acceptance/', 1)
FROM read_text('specs/components/*/acceptance/*.md', filename:=true)
UNION ALL
SELECT UNNEST(regexp_extract_all(content, '### (GS-[A-Za-z0-9-]+)', 1)), NULL, NULL, 'golden_scenario', NULL
FROM read_text('specs/product/*.md', filename:=true);
```

The first four kinds (`component`/`capability`/`var`/`guarantee`) fix a
gap `R-IMPACT-009`'s original wording left open: that wording named only
the three frontmatter sources, with no mechanism for enumerating
guarantee nodes at all — the target side of a `depends_on_guarantees`
edge was never actually resolvable against a real node, only assumed to
exist. `owner_component_id` is what lets `spec-linter`'s R-LINT-018 check
(below) be a plain join instead of bespoke path-parsing; it's `NULL` for
`golden_scenario` rows since their parent is a capability, not a
component — the `covers` edge below carries that relationship instead.

**`edges`** — one row per `(source_id, target_id, edge_type)`. The first
four edge types are unnested from each component's list-valued
frontmatter fields; `covers` is extracted from `Covers:` lines in
requirement-traceability files' body text (`spec-linter`'s
`rule_forward_traceability`/`rule_backward_traceability`, R-LINT-008/009)
rather than from frontmatter, since that's where `Covers:` actually
lives — a component-acceptance file carries exactly one (D15: the file
*is* one criterion), a product file carries one per golden scenario,
paired with the heading immediately above it:

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
FROM read_yaml_frontmatter('specs/components/*/component.md')
UNION ALL
SELECT
  regexp_extract(filename, '(AC-[A-Za-z0-9-]+)\.md$', 1),
  regexp_extract(content, 'Covers:\s*(\S+)', 1), 'covers'
FROM read_text('specs/components/*/acceptance/*.md', filename:=true)
UNION ALL
SELECT m['gs_id'], m['target'], 'covers'
FROM (
  SELECT UNNEST(regexp_extract_all(
    content, '### (GS-[A-Za-z0-9-]+)\s*\nCovers:\s*(\S+)', ['gs_id', 'target']
  )) AS m
  FROM read_text('specs/product/*.md', filename:=true)
);
```

**The last `edges` branch is the one genuinely harder piece of this
corpus's DuckDB adoption** — pairing a golden scenario's heading with
its own `Covers:` line in one pass, rather than the clean "one row per
file" shape every other view here has. Flagged plainly rather than
glossed over: the exact capture-group extraction function/signature
above is illustrative of intent, same as every other SQL sketch in this
document, but implementing this branch is where that gap between
sketch and working query is most likely to need real adjustment.

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

**`component_provenance`** — one row per component, read directly from
the provenance manifests `provenance-writer` already writes
(`verification/<component>/.provenance.json`), which already embed
`verification_report`, `license_scan`, `secret_scan`, and `cache_hit`
(`SPEC_GUIDELINES.md` §7):

```sql
CREATE VIEW component_provenance AS
SELECT
  'comp-' || regexp_extract(filename, 'verification/([^/]+)/\.provenance\.json$', 1)
    AS component_id,
  *
FROM read_json('verification/*/.provenance.json', filename:=true);
```

Not graph-shaped — it uses neither `yaml` nor `duckpgq`, just core
`read_json` — and originally lived only inside `corpus-graph-builder`'s
own spec (`R-GRAPH-009`) on the premise that no other component needed
it. That premise held only until `review-packet-builder` (`R-PACKET-011`,
D26) needed the exact same thing: every field its `ReviewPacket` reports
per component (`verification_results`, `compliance_flags`,
`cache_hit_status`) is already in this manifest. Promoted here once a
second consumer appeared, for the same reason `nodes`/`edges` exist as
one shared definition instead of two independently-written ones.

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
  are joins and aggregates against `nodes`/`edges`/`component_provenance`
  plus `component_size`, the one view still scoped to this component
  alone (see `R-GRAPH-009`). Its JSON-writing role is unchanged
  (R-GRAPH-006/008: `verification/corpus-graph.json` is still a
  committed, deterministic artifact — only the *construction* step, not
  the output format, moves onto this engine).
- **`golden-scenario-verifier`'s capability-intersection lookup**
  (`R-GOLDEN-002`) — "every product capability whose `realizes`-set
  intersects the blast radius" is a single query against `edges`, not a
  bespoke intersection written once for this call site. This logic
  originally lived in `merge-orchestrator` as `R-MERGE-020`; it moved
  with the rest of the golden-scenario gate when D25 extracted
  `golden-scenario-verifier` out of `merge-orchestrator` to relieve that
  component's fan-out/word-count caps.
- **`review-packet-builder`** (`R-PACKET-011`) — every field it reports
  from `verifier-orchestrator`/`license-scanner`/`secret-scanner`/
  `cache-manager` is read via `component_provenance` instead of a live
  call into any of them, since `provenance-writer` (which it already
  depended on) already collected all of it. Dropped its `depends_on`
  from 5 to 1 (D26).
- **`spec-linter`'s requirement-traceability rules**
  (`rule_forward_traceability`/R-LINT-008, `rule_backward_traceability`/
  R-LINT-009, `R-LINT-021`, D27) — originally flagged below as a
  distinct, deferred candidate because it appeared to need a second graph
  vocabulary (`R-id`/`AC-id`/`GS-id` nodes). Reading `spec_linter.py`'s
  actual implementation showed the real need is smaller: R-LINT-008 only
  counts `covers`-edges per requirement, R-LINT-009 only validates each
  edge's *target* against `nodes` — neither needs `AC-id`/`GS-id` as
  addressable nodes for its own check to work. D27 adopted the fuller
  shape anyway (`requirement`/`acceptance`/`golden_scenario` all modeled
  as proper `nodes`, not just the minimum each rule strictly needs), for
  a complete graph rather than one trimmed to today's two consumers.

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
