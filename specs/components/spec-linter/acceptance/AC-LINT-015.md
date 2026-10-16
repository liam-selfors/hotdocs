# AC-LINT-015

Covers: R-LINT-015
Kind: llm-judge

The one criterion in this component that is not `kind: compiled` or
`generated-test` — by design, matching D5's own guidance that `llm-judge` is
for qualities no test could capture even in principle. Detecting a
*structural* restatement (R-LINT-011) is mechanical; detecting that two
differently-worded passages mean *conflicting* things is not.

```gherkin
Given a component's Definitions section whose entry for a glossary term uses
  substantially different wording from specs/glossary.md's definition (so
  R-LINT-011's textual-similarity check does not fire), but asserts something
  that actually contradicts that definition
When hotdocs lint runs against the component with a model configured
Then the report contains a fail-severity finding for rule R-LINT-015, with a
  structured rationale explaining the conflict
```
