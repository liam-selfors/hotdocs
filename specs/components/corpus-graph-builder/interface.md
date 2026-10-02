---
id: comp-corpus-graph-builder-interface
title: Corpus Graph Builder — Interface
status: draft
owners: [pipeline-team]
---

# Corpus Graph Builder — Interface

## CLI

```
hotdocs corpus-graph build [--repo-root=<dir>]
```

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | `verification/corpus-graph.json` written. |
| `1` | A required upstream result was missing. |
| `2` | Usage error. |

## Library

```
build_corpus_graph(repo_root: Path) -> CorpusGraph
```

## Data: `CorpusGraph`

```json
{
  "nodes": {
    "P-ZERO-EDIT": { "type": "capability" },
    "comp-foo": {
      "type": "component",
      "verification": { "...": "a VerificationReport" },
      "provenance": { "...": "a provenance manifest" },
      "size_status": "ok",
      "sealed": false,
      "pinned_overrides": []
    },
    "VAR-FOO-URL": { "type": "var" }
  },
  "edges": [
    { "from": "comp-foo", "to": "comp-bar", "kind": "depends_on" },
    { "from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes" },
    { "from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var" }
  ],
  "aggregates": {
    "orphan_capability_rate": 0.0,
    "orphan_component_rate": 0.0,
    "orphan_var_rate": 0.0
  }
}
```
