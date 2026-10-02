---
id: comp-docs-site-renderer-acceptance
title: Docs Site Renderer — Acceptance Criteria
status: draft
owners: [pipeline-team]
---

# Docs Site Renderer — Acceptance Criteria

All six criteria are `kind: compiled` — rendering already-computed data is
pure, deterministic templating. An eleventh component in this corpus with a
fully `compiled` acceptance set.

### AC-DOCS-001
Covers: R-DOCS-001
Kind: compiled

```gherkin
Given a corpus-graph.json with three nodes and two edges
When render_docs_site runs
Then the rendered site's DAG view contains three node elements and two edge
  elements
```

### AC-DOCS-002
Covers: R-DOCS-002
Kind: compiled

```gherkin
Given a component node carrying a full detail payload (spec content,
  R-ids, criteria, provenance, size status, toggle state, sealed status,
  owners)
When render_docs_site runs
Then that component's detail view includes every one of those fields
```

### AC-DOCS-003
Covers: R-DOCS-003
Kind: compiled

```gherkin
Given corpus-graph.json's aggregates field with known metric values
When render_docs_site runs
Then the dashboard view displays those exact values
```

### AC-DOCS-004
Covers: R-DOCS-004
Kind: compiled

```gherkin
Given only corpus-graph.json as input, with no other files available
When render_docs_site runs
Then it completes successfully, reading nothing else
```

### AC-DOCS-005
Covers: R-DOCS-005
Kind: compiled

```gherkin
Given a successful render
When the repository's committed files are checked
Then the rendered output directory is absent from version control
```

### AC-DOCS-006
Covers: R-DOCS-006
Kind: compiled

```gherkin
Given a render run
When it executes
Then no network call or model call occurs at any point
```
