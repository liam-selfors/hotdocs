# AC-ASSEMBLE-018

Covers: R-ASSEMBLE-009
Kind: generated-test

```gherkin
Given the library's test fixture with
  specs/components/foo/testing.md written as
  "Uses: `specs/architecture/fix.md`\n\nPlant X.\n" and
  specs/architecture/fix.md written as "Fixture rules.\n"
When assemble_criterion runs for comp-foo and its first criterion
Then the bundle's testing is exactly "Uses: `specs/architecture/fix.md`\n\nPlant X.\n\n## Uses: specs/architecture/fix.md\n\nFixture rules.\n"
  and assemble's SpecBundle
  for comp-foo contains neither "Plant X." nor "Fixture rules."

Given the same fixture without testing.md
When assemble_criterion runs
Then the bundle's testing is ""

Given testing.md naming "Uses: `specs/architecture/missing.md`"
When assemble_criterion runs
Then it raises PreconditionFailure
```
