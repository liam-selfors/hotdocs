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
  "vars": { "VAR-FOO-URL": "<the var declaration's body>" },
  "glossary": "<specs/glossary.md body>",
  "hint_code": null
}
```

`hint_code` is `null` in `cold` mode; in `hint` mode it holds the component's
current `gen/<component>/` file contents, keyed by relative path.

`dependency_context` (R-ASSEMBLE-010, D35) is deliberately a separate
field from `dependency_interfaces`, not a richer shape for the same
one — `dependency_interfaces` stays exactly what R-ASSEMBLE-002 already
defines it as (the contract), and `dependency_context` is the one
narrow exception on top of it (the dependency's `Purpose` text only).
Keyed the same way, by `component_id`, for every id in `depends_on`.
