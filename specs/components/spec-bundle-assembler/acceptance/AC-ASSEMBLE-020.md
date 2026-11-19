# AC-ASSEMBLE-020

Covers: R-ASSEMBLE-016
Kind: generated-test

```gherkin
Given the library's asset fixture, with no specs/asset-kinds/ under repo_root
When assemble and assemble_criterion run for comp-foo and AC-FOO-001
Then the SpecBundle's interface ends with
  "\n\n## Asset kind: javascript\n\n" + G
  and the CriterionBundle's testing is exactly
  "\n## Asset kind: javascript\n\n" + T,
  G and T the "Generator guidance" and "Test author guidance" sections
  of the tool root's specs/asset-kinds/javascript.md

Given the asset fixture with foo's assets "[nokind:static/x.txt]"
When assemble runs
Then it raises PreconditionFailure
```
