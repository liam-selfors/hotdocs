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
  }
}
```

Assembled by `spec-bundle-assembler` (a new library entry point alongside
`assemble()`, narrower in scope and never including `gen/<component>/`
content, per R-AUTHOR-002). `dependency_interfaces` (`D100`) is keyed by
every id in the target component's own `depends_on`, each value that
dependency's full `interface/` content — the same content and the same
`R-ASSEMBLE-002` rule `SpecBundle.dependency_interfaces` already
follows. This is a third party's already-public, already-documented
contract, never the target's own implementation, so it does not reopen
`R-AUTHOR-002`'s independence boundary; without it, a test faking a
dependency's behavior has no authoritative source for that
dependency's real call signature or return shape and must guess
(`D100`).
