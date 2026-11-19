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

Given the library's project-kind asset fixture with its kind renamed
  "nokind" throughout (specs/architecture/asset-kind-nokind.md,
  component comp-kind-nokind, foo's assets "[nokind:static/app.js]" and
  depends_on [comp-kind-nokind]) and no gen/kind-nokind/ anywhere, so
  the corpus lints clean but the kind has no adapter
When assemble runs
Then it raises PreconditionFailure whose message is
  "unknown asset kind: nokind"
```
