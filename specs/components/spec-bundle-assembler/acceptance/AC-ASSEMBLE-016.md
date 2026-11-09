# AC-ASSEMBLE-016

Covers: R-ASSEMBLE-014
Kind: generated-test

```gherkin
Given the library's test fixture, plus specs/architecture/rules.md (the
  frontmatter id arch-rules, title Rules, status draft, owners [team-a],
  depends_on [], then the body "# Rules" and "Foo rounds down."), and
  comp-foo's interface/library.md gaining the line
  Implements: `specs/architecture/rules.md`
When assemble and assemble_criterion run for comp-foo
Then each bundle's interface contains the line
  "## Implements: specs/architecture/rules.md", and after it that file's
  full text, which ends the interface once trailing whitespace is
  stripped

Given the line names `specs/architecture/missing.md` instead
When assemble runs for comp-foo
Then it raises PreconditionFailure
```
