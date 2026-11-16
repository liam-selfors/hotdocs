# `CorpusGraph`

```json
{
  "nodes": {
    "P-ZERO-EDIT": { "type": "capability" },
    "comp-foo": {
      "type": "component",
      "verification": { "...": "the manifest's verification_report" },
      "provenance": { "...": "the manifest's other top-level fields" },
      "size_status": "ok",
      "sealed": false,
      "pinned_overrides": [],
      "owners": ["pipeline-team"],
      "documents": { "component.md": "<its text>", "requirements/R-FOO-001.md": "<its text>" }
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

`nodes` is keyed by id and holds only components, capabilities and
vars (never requirements, criteria or decisions). `edges` holds only
the three kinds shown, sorted by `from`, then `to`, then `kind`.

A component node's `verification` and `provenance` come from
`verification/<slug>/.provenance.json` read with `json.load`, so every
value is the file's own JSON (`generated_at` stays the string written
there): `verification` is its `verification_report`, `provenance` every
other top-level key. With no manifest both are `null`. `size_status` is
`"ok"` when the component's `component_size` word count is at most
`4000`, `"over"` above it, `"unknown"` with no row. `sealed` is the
frontmatter's `sealed` (absent is `false`). `pinned_overrides` is the
JSON list in `gen/<slug>/.overrides.json`, else `[]` (no file, or not a
list). `owners` is the frontmatter's `owners` list (absent is `[]`).
`documents` maps each `.md` file under `specs/components/<slug>/`, by its
path relative to that directory with `/` separators, to its whole text,
keys sorted.

Each rate is a count divided by a total, `0.0` when the total is `0`:
capabilities with no incoming `realizes` edge over all capabilities;
vars with no incoming `uses_var` edge over all vars; components with
neither an incoming `depends_on` edge nor an outgoing `realizes` edge
over all components.
