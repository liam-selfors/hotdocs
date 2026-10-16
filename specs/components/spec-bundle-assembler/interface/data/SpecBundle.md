# `SpecBundle`

```json
{
  "component_id": "comp-foo",
  "spec_bundle_hash": "sha256:...",
  "spec": "<component.md body + requirements/ content>",
  "interface": "<interface/ content>",
  "constraints": "<constraints.md body>",
  "dependency_interfaces": { "comp-bar": "<bar/interface/ content>" },
  "vars": { "VAR-FOO-URL": "<the var declaration's body>" },
  "glossary": "<specs/glossary.md body>",
  "hint_code": null
}
```

`hint_code` is `null` in `cold` mode; in `hint` mode it holds the component's
current `gen/<component>/` file contents, keyed by relative path.
