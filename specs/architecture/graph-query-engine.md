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
this document names six views as the one shared surface all of them
query. A component MAY define additional views of its own for data no
other component needs, but MUST NOT redefine these six — and if a
second component ever needs one of its own local views, that is the
signal to promote it here instead, same as `component_provenance` and
`component_size`'s own history.

**`nodes`** — one row per spec id in the corpus, across seven kinds.
Components, product capabilities, and vars come from their own
frontmatter; **guarantees, requirements, and acceptance criteria carry no
frontmatter at all** (D15 — unit-file identity is the filename, not a
`---` block), so those rows are built from `read_text()` and filenames
alone, with `owner_component_id` extracted from path rather than read
from any field. **Capability scenarios are the one kind with no file of
their own** — they're `### CS-...` headings inside a product
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
FROM read_text('specs/components/*/interface/guarantees/*.md')
UNION ALL
SELECT
  regexp_extract(filename, '(R-[A-Za-z0-9-]+)\.md$', 1), NULL, NULL, 'requirement',
  'comp-' || regexp_extract(filename, 'specs/components/([^/]+)/requirements/', 1)
FROM read_text('specs/components/*/requirements/*.md')
UNION ALL
SELECT
  regexp_extract(filename, '(AC-[A-Za-z0-9-]+)\.md$', 1), NULL, NULL, 'acceptance',
  'comp-' || regexp_extract(filename, 'specs/components/([^/]+)/acceptance/', 1)
FROM read_text('specs/components/*/acceptance/*.md')
UNION ALL
SELECT UNNEST(regexp_extract_all(content, '### (CS-[A-Za-z0-9-]+)', 1)), NULL, NULL, 'capability_scenario', NULL
FROM read_text('specs/product/*.md');
```

`read_text` already returns `filename` unconditionally — unlike
`read_yaml_frontmatter`, it has no `filename:=true` parameter and
errors if given one (`D43`; confirmed by actually running this view,
which could not be created as originally written). Once fixed,
verified against this repo's real corpus: 21 `component`, 4
`capability`, 4 `var`, 1 `guarantee`, 201 `requirement`, 227
`acceptance`, 4 `capability_scenario` — each count cross-checked
against an independent file-system count, exact match.

The first four kinds (`component`/`capability`/`var`/`guarantee`) fix a
gap `R-IMPACT-009`'s original wording left open: that wording named only
the three frontmatter sources, with no mechanism for enumerating
guarantee nodes at all — the target side of a `depends_on_guarantees`
edge was never actually resolvable against a real node, only assumed to
exist. `owner_component_id` is what lets `spec-linter`'s R-LINT-018 check
(below) be a plain join instead of bespoke path-parsing; it's `NULL` for
`capability_scenario` rows since their parent is a capability, not a
component — the `covers` edge below carries that relationship instead.

**`edges`** — one row per `(source_id, target_id, edge_type)`. The first
four edge types are unnested from each component's list-valued
frontmatter fields; `covers` is extracted from `Covers:` lines in
requirement-traceability files' body text (`spec-linter`'s
`rule_forward_traceability`/`rule_backward_traceability`, R-LINT-008/009)
rather than from frontmatter, since that's where `Covers:` actually
lives — a component-acceptance file carries exactly one (D15: the file
*is* one criterion), a product file carries one per capability scenario,
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
FROM read_text('specs/components/*/acceptance/*.md')
UNION ALL
SELECT m['cs_id'], m['target'], 'covers'
FROM (
  SELECT UNNEST(regexp_extract_all(
    content, '### (CS-[A-Za-z0-9-]+)\s*\nCovers:\s*(\S+)', ['cs_id', 'target']
  )) AS m
  FROM read_text('specs/product/*.md')
);
```

**The last `edges` branch turned out to be the one piece of this
corpus's DuckDB adoption that worked on the first try** (`D43`) —
flagged in an earlier draft of this section as the part most likely to
need real adjustment once actually implemented; running it against
real DuckDB found the opposite was true, and the two `read_text`
calls above it were the ones that needed fixing instead. Verified
against this repo's real corpus: 231 `covers` edges total (227 from
`acceptance/` files, 4 from capability scenarios), matching an
independent file-count check exactly.

**`component_docs`** — one row per component, frontmatter fields joined
with the file's full raw text (frontmatter included), for anything that
needs structure and prose together rather than just the graph shape:

```sql
CREATE VIEW component_docs AS
SELECT fm.*, t.content AS body
FROM read_yaml_frontmatter('specs/components/*/component.md', filename:=true) fm
JOIN read_text('specs/components/*/component.md') t USING (filename);
```

`component_docs` is the data layer, not the rendered output — it answers
"what does this component's frontmatter and prose say," not "what should
a human see." Assembling an actual compiled, cross-linked document
(ordering sections, turning ids into hyperlinks) is still
`docs-site-renderer`'s job, the same way `merge-tracker-ui` renders
`merge-tracker`'s data rather than the data layer doing its own
presentation.

**`component_context`** — one row per component, just its `Purpose`
section's text, extracted from `component_docs` the same way
`rule_ratified_closure` already extracts `Open questions` for
`R-LINT-002`:

```sql
CREATE VIEW component_context AS
SELECT
  id AS component_id,
  regexp_extract(body, '##\s*Purpose\s*\n(.*?)\n##', 1, 's') AS purpose
FROM component_docs;
```

The `'s'` flag (`D43`) is load-bearing, not stylistic: without it,
`.` does not match newlines, so a multi-line `Purpose` section (nearly
all of them) silently extracts to an empty string instead of failing
loudly — found only by actually running this view and checking its
output, not by reading the SQL. The equivalent Python
(`spec_linter.py`'s `_extract_purpose`) already passes `re.DOTALL`;
this view's SQL had drifted from that without anyone noticing, since
nothing had ever executed it.

Deliberately narrower than `component_docs` — this is the one slice of
a component's own file that's safe to hand to a *dependent*
(`spec-bundle-assembler`'s `R-ASSEMBLE-010`, `D35`), because `D34`
made `Purpose` dependent-safe by construction (no decision citations,
no historical rationale — enforced by `R-LINT-024`) and nothing else
in `component.md` carries that guarantee. `requirements/`,
`constraints.md`, and the rest of `component.md` stay exactly as
excluded as `R-ASSEMBLE-002` already says; this view does not, and
must not, become a way around that boundary for anything but `Purpose`
specifically.

**`component_provenance`** — one row per component, read directly from
the provenance manifests `provenance-writer` already writes
(`verification/<component>/.provenance.json`), which already embed
`verification_report`, `license_scan`, `secret_scan`, and
`provenance_hit` (`SPEC_GUIDELINES.md` §7):

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
`provenance_hit_status`) is already in this manifest. Promoted here once a
second consumer appeared, for the same reason `nodes`/`edges` exist as
one shared definition instead of two independently-written ones.

**`component_size`** — one row per component, the word count
`R-LINT-012`'s `component_doc_words` dimension measures:

```sql
CREATE VIEW component_size AS
SELECT
  'comp-' || regexp_extract(filename, 'specs/components/([^/]+)/', 1) AS component_id,
  sum(len(list_filter(
    regexp_split_to_array(
      trim(regexp_replace(content, '^---\n.*?\n---\n', '', 's')),
      '\s+'
    ),
    lambda x: x != ''
  ))) AS word_count
FROM read_text('specs/components/*/**/*.md')
GROUP BY 1;
```

Promoted here the same way, by the same rule, once `spec-linter`
(`D42`) became this view's first *real* consumer rather than a second
independently-written algorithm: `rule_size_caps` previously computed
`component_doc_words` via its own Python loop over `corpus.docs`,
right alongside `corpus-graph-builder`'s already-specced (but, until
`D42`, never actually implemented) `component_size` view — the same
"two parsers, one graph" risk `R-LINT-020`'s own rationale already
warns about, just for word-counting instead of reference resolution.
`D42` also fixed two latent bugs the original SQL carried, found only
by actually running it against real DuckDB rather than taking the
written SQL on faith: `read_text` has no `filename:=true` parameter
(that's a `read_json`/`read_csv`-only keyword — `component_provenance`
above uses it correctly; this view never needed it, since
`regexp_extract` can pull the component id from the `filename` column
`read_text` already returns unconditionally), and `trim()` without an
explicit character set strips spaces only, not newlines — producing a
spurious trailing empty token on every file's split that inflated
every component's count by exactly one. Both fixes are already folded
into the SQL above, verified word-for-word against `spec-linter`'s own
prior Python computation before the switch (zero mismatches across
all 21 components).

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
  component alone (`D42` promoted the last one). Its JSON-writing role
  is unchanged (R-GRAPH-006/008: `verification/corpus-graph.json` is
  still a committed, deterministic artifact — only the *construction*
  step, not the output format, moves onto this engine).
- **`spec-linter`'s size-cap rule** (`rule_size_caps`/`R-LINT-012`,
  `D42`) — `component_doc_words` is this view's `word_count`, queried
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
  with the rest of the capability-scenario gate when D25 extracted
  `capability-scenario-verifier` (named `golden-scenario-verifier` at
  the time; renamed by `D36`) out of `merge-orchestrator` to relieve
  that component's fan-out/word-count caps.
- **`review-packet-builder`** (`R-PACKET-011`) — every field it reports
  from `verifier-orchestrator`/`license-scanner`/`secret-scanner` is
  read via `component_provenance` instead of a live call into any of
  them, since `provenance-writer` (which it already depended on)
  already collected all of it. Dropped its `depends_on`
  from 5 to 1 (D26).
- **`spec-linter`'s requirement-traceability rules**
  (`rule_forward_traceability`/R-LINT-008, `rule_backward_traceability`/
  R-LINT-009, `R-LINT-021`, D27) — originally flagged below as a
  distinct, deferred candidate because it appeared to need a second graph
  vocabulary (`R-id`/`AC-id`/`GS-id` nodes — `GS-id` renamed `CS-id` by
  `D36`). Reading `spec_linter.py`'s actual implementation showed the
  real need is smaller: R-LINT-008 only counts `covers`-edges per
  requirement, R-LINT-009 only validates each edge's *target* against
  `nodes` — neither needs `AC-id`/`CS-id` as addressable nodes for its
  own check to work. D27 adopted the fuller
  shape anyway (`requirement`/`acceptance`/`capability_scenario` all modeled
  as proper `nodes`, not just the minimum each rule strictly needs), for
  a complete graph rather than one trimmed to today's two consumers.
- **`spec-bundle-assembler`** (`R-ASSEMBLE-010`, `D35`) — each
  dependency's `Purpose` text, handed to a dependent as
  `dependency_context`, is read via `component_context` rather than
  reaching into the dependency's `component.md` directly. A narrow,
  explicit exception to `R-ASSEMBLE-002`'s otherwise-correct "never
  `component.md`" rule, scoped to exactly the one section `D34` made
  dependent-safe by construction.

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
