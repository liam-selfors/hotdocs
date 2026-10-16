# `CorpusGraph`

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
