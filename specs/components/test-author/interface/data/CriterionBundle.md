# `CriterionBundle`

```json
{
  "component_id": "comp-foo",
  "criterion_id": "AC-FOO-003",
  "covers": "R-FOO-003",
  "criterion_text": "<Given/When/Then prose>",
  "requirement_text": "<the covered R-id's own text from requirements/>",
  "interface": "<interface/ content>",
  "glossary": "<specs/glossary.md body>"
}
```

Assembled by `spec-bundle-assembler` (a new library entry point alongside
`assemble()`, narrower in scope and never including `gen/<component>/`
content, per R-AUTHOR-002).
