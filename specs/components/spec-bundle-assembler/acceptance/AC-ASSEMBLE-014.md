# AC-ASSEMBLE-014

Covers: R-ASSEMBLE-012
Kind: generated-test

```gherkin
Given every .py file of the module under test, found from the imported
  module's __file__ (a package's whole directory)
When each is parsed with ast
Then none imports yaml, ruamel, markdown, mistune, frontmatter or
  commonmark, and at least one contains a call whose function is an
  attribute named load_corpus — spec-linter is loaded at runtime from
  repo_root, never imported by name, so no import of spec_linter is
  expected
```
