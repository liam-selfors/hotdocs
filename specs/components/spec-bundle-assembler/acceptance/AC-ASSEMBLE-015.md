# AC-ASSEMBLE-015

Covers: R-ASSEMBLE-013
Kind: generated-test

```gherkin
Given a component depending on comp-bar, whose own interface/ content
  names a type "Widget" that comp-bar does not itself own, and a
  separate component comp-baz that does own interface/data/Widget.md
When assemble_criterion runs for the dependent component
Then dependency_interfaces["comp-bar"] contains both comp-bar's own
  interface content and, clearly labeled as owned by comp-baz,
  Widget's own documented content

Given a component depending on comp-bar, whose interface/ content
  names a type with no owner anywhere in the corpus
When assemble_criterion runs
Then dependency_interfaces["comp-bar"] contains comp-bar's own
  content unchanged, with no fabricated section for the unresolved
  name

Given a component depending on comp-bar, whose interface/ content
  names a type two different components both claim to own
When assemble_criterion runs
Then dependency_interfaces["comp-bar"] contains comp-bar's own
  content unchanged, with no section for the ambiguous name
```
