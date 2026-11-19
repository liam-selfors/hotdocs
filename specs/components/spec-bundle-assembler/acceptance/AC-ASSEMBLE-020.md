# AC-ASSEMBLE-020

Covers: R-ASSEMBLE-016
Kind: generated-test

```gherkin
Given the library's asset fixture, with no gen/kind-javascript/ under repo_root
When assemble and assemble_criterion run for comp-foo and AC-FOO-001
Then the SpecBundle's interface ends with
  "\n\n## Asset kind: javascript\n\n" + G
  and the CriterionBundle's testing is exactly
  "\n## Asset kind: javascript\n\n" + T,
  G and T the stripped "generator" and "test_author" values of the
  tool's own adapter's guidance()

Given the asset fixture with foo's assets "[nokind:static/x.txt]"
When assemble runs
Then it raises PreconditionFailure whose message is
  "unknown asset kind: nokind"
```
