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
  "dependency_interfaces": { "comp-bar": "<bar/interface/ content>" },
  "testing": "<testing.md and its Uses: documents, or \"\">"
}
```

A dataclass with these fields in this order, `dependency_interfaces`
defaulting to `{}` and `testing` to `""`, that also reads as a mapping (`bundle["covers"]`,
`bundle.get("covers")`), as `SpecBundle` does.

Narrower than `SpecBundle` by design (R-ASSEMBLE-009) — `test-author`'s
consumer of this schema.
