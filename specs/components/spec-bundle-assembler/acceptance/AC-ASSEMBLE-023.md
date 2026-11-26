# AC-ASSEMBLE-023

Covers: R-ASSEMBLE-007
Kind: generated-test

```gherkin
Given the library's test fixture with a dependent comp-baz
When assemble("comp-baz") runs before and after each of these edits,
  each alone: comp-baz's component.md gains a final section
  "## Change log\n\n- D1.\n"; comp-foo's component.md gains a final
  section "## Scope\n\nAll of it.\n"
Then each edit leaves spec_bundle_hash unchanged

When assemble("comp-baz") runs before and after each of these edits,
  each alone: comp-baz's component.md gains a final section
  "## Scope\n\nAll of it.\n"; comp-foo's Purpose text "Foo doubles a
  number." becomes "Foo triples a number."
Then each edit changes spec_bundle_hash
```
