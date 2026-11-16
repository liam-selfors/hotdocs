# AC-ASSEMBLE-009

Covers: R-ASSEMBLE-009
Kind: generated-test

```gherkin
Given a component with existing gen/<component>/ content and a multi-
  criterion acceptance/ directory
When assemble_criterion runs for one specific criterion
Then the resulting CriterionBundle contains that criterion's text, its
  covered requirement's text, the interface, and the glossary — and
  contains no field derived from gen/<component>/, any other file under
  requirements/, or constraints.md
```
