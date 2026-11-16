# `CriterionBundle`

```json
{
  "component_id": "comp-foo",
  "criterion_id": "AC-FOO-003",
  "covers": "R-FOO-003",
  "criterion_text": "<Given/When/Then prose>",
  "requirement_text": "<the covered R-id's own text from requirements/>",
  "interface": "<interface/ content>",
  "glossary": "<specs/glossary.md body>",
  "dependency_interfaces": {
    "comp-bar": "<comp-bar's own interface/ content>"
  },
  "module_names": ["foo"]
}
```

Assembled by `spec-bundle-assembler`'s narrow entry point, never with
`gen/<component>/` content (`R-AUTHOR-002`). `dependency_interfaces`
(`D100`) is keyed by every id in the target's `depends_on`, each value
that dependency's full `interface/` content (`R-ASSEMBLE-002`): a
public contract, so a fake can match the real signature and return
shape instead of guessing. `module_names` is optional and read with a
default, since the assembler's bundles do not carry it
(`R-AUTHOR-026`).
