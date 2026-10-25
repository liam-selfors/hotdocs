# R-GRAPH-009

**R-GRAPH-009** — R-GRAPH-001/002 (node/edge construction) MUST be built
  from the `nodes`/`edges` views named in `specs/architecture/
  graph-query-engine.md`'s "Query surface" section — the same views
  `impact-analyzer` (R-IMPACT-009) and `spec-linter` (R-LINT-020) use —
  not a third, independently-written graph-construction step.

  R-GRAPH-003's per-node annotations and R-GRAPH-004/005's corpus-wide
  orphan rates MUST be computed as joins and aggregates against
  `nodes`/`edges` plus two views scoped to this component alone (no other
  component needs verification/provenance/size data joined onto the
  graph, so these do not belong in the shared architecture doc):

  - **`component_provenance`** — one row per component, read directly
    from the provenance manifests `provenance-writer` already writes
    (`verification/<component>/.provenance.json`), which already embed
    `verification_report`, `license_scan`, `secret_scan`, and `cache_hit`
    (`SPEC_GUIDELINES.md` §7) — no separate read of
    `verifier-orchestrator`'s, `license-scanner`'s, or `secret-scanner`'s
    output is needed, since none of them write their own file:

    ```sql
    CREATE VIEW component_provenance AS
    SELECT
      'comp-' || regexp_extract(filename, 'verification/([^/]+)/\.provenance\.json$', 1)
        AS component_id,
      *
    FROM read_json('verification/*/.provenance.json', filename:=true);
    ```

  - **`component_size`** — one row per component, the spec-bundle word
    count R-LINT-012/D2 already defines (component.md + requirements/ +
    interface/ (+ data/, + guarantees/) + acceptance/ + constraints.md,
    as authored), computed the same way `spec_linter.py`'s
    `rule_size_caps` already does (`len(body.split())` summed per file)
    — this view MUST reuse that exact counting method, not introduce a
    second one that could disagree with the one `spec-linter` enforces:

    ```sql
    CREATE VIEW component_size AS
    SELECT
      'comp-' || regexp_extract(filename, 'specs/components/([^/]+)/', 1) AS component_id,
      sum(len(regexp_split_to_array(trim(content), '\s+'))) AS word_count
    FROM read_text('specs/components/*/**/*.md', filename:=true)
    GROUP BY 1;
    ```

  This is an implementation requirement, not a behavioral one —
  R-GRAPH-001 through 008 are unaffected; R-GRAPH-006/008 (the committed,
  deterministic `verification/corpus-graph.json` output) are unchanged —
  only the graph- and annotation-*construction* steps move onto this
  engine, not the output format or its determinism obligation.
