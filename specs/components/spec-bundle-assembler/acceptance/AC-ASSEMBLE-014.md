# AC-ASSEMBLE-014

Covers: R-ASSEMBLE-012
Kind: generated-test

```gherkin
Given the real, committed spec_bundle_assembler.py source
When its import statements are inspected
Then it imports no standalone YAML- or Markdown-parsing third-party
  package, and its corpus-reading logic calls spec-linter's own
  load_corpus rather than re-parsing any component.md frontmatter
  directly
```
