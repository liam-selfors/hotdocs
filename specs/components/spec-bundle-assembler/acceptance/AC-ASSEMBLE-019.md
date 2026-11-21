# AC-ASSEMBLE-019

Covers: R-ASSEMBLE-016
Kind: generated-test

```gherkin
Given the library's project-kind asset fixture
When assemble runs for comp-foo
Then its interface contains "export function double(x)"
  and ends with "\n\n## Asset kind: javascript\n\nGenerator guidance text."
  and no field of the SpecBundle contains "Test author guidance text."

When assemble_criterion runs for comp-foo and AC-FOO-001
Then the bundle's testing is exactly "\n## Asset kind: javascript\n\nTest author guidance text."
  and its interface contains "export function double(x)"
  but not "Generator guidance text."

Given the same fixture with specs/components/foo/testing.md written as "Plant X.\n"
When assemble_criterion runs
Then the bundle's testing is exactly "Plant X.\n\n## Asset kind: javascript\n\nTest author guidance text."
```
