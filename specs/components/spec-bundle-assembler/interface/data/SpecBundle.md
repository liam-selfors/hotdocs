# `SpecBundle`

```json
{
  "component_id": "comp-foo",
  "spec_bundle_hash": "sha256:...",
  "spec": "<component.md body + requirements/ content>",
  "interface": "<interface/ content>",
  "constraints": "<constraints.md body>",
  "dependency_interfaces": { "comp-bar": "<bar/interface/ content>" },
  "dependency_context": { "comp-bar": "<bar's Purpose section text>" },
  "dependency_usage": { "comp-bar": "<bar's real, importable module path + public symbol signatures/docstrings, or \"\" if bar has no real code yet>" },
  "vars": { "VAR-FOO-URL": "<the var declaration's body>" },
  "glossary": "<specs/glossary.md body>",
  "hint_code": null
}
```

`hint_code` is `null` in `cold` mode; in `hint` mode it holds the component's
current `gen/<component>/` file contents, keyed by relative path.

`dependency_context` (R-ASSEMBLE-010, D22) is deliberately a separate
field from `dependency_interfaces`, not a richer shape for the same
one — `dependency_interfaces` stays exactly what R-ASSEMBLE-002 already
defines it as (the contract), and `dependency_context` is the one
narrow exception on top of it (the dependency's `Purpose` text only).
Keyed the same way, by `component_id`, for every id in `depends_on`.

`dependency_usage` (R-ASSEMBLE-011, `D37`) is a third, independent field
alongside the two above — mechanically introspected from a dependency's
real `gen/<dependency>/` code (never from its spec, the reverse of every
other `dependency_*` field), empty for a dependency with no real code
yet. Deliberately one-directional: nothing in this bundle ever carries
information the other way, from a component's dependents back toward
the component itself — see `R-ASSEMBLE-011` for why that direction was
considered and rejected.
