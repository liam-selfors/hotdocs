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
  "hint_code": null,
  "spec_bundle_parts": {"spec": "sha256:...", "dependency_code": "sha256:..."}
}
```

`hint_code` is `null` in `cold` mode; in `hint` mode it holds the component's
current `gen/<component>/` file contents, keyed by relative path.

A dataclass with these fields in this order (the four dicts and
`spec_bundle_parts` default to `{}`, `glossary` to `""`, `hint_code` to `None`) that also reads as a
read-only mapping: `bundle["spec"]` and `bundle.get("spec")` work.
Each text field joins its documents' bodies, each stripped, empty ones
dropped, with one blank line between. `interface` ends with any
documents `R-ASSEMBLE-014` appends, then
`R-ASSEMBLE-016`'s asset-kind generator guidance.
`dependency_context` (`R-ASSEMBLE-010`) holds each dependency's `Purpose`
only. `dependency_usage` (`R-ASSEMBLE-011`) is introspected from a
dependency's real code, `""` when it has none, and nothing flows the
other way. `spec_bundle_hash` and `spec_bundle_parts` are defined in `R-ASSEMBLE-007`.
