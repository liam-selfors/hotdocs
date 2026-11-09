# AC-ASSEMBLE-013

Covers: R-ASSEMBLE-009
Kind: generated-test

```gherkin
Given a component that depends_on another component with its own
  component.md, requirements/, interface/, and constraints.md
When assemble_criterion runs for one of the dependent's own criteria
Then the resulting CriterionBundle's dependency_interfaces contains an
  entry keyed by the dependency's id whose value contains the text of
  each of that dependency's interface/ files, and contains no line
  unique to its component.md, requirements/ or constraints.md

Given a component with no depends_on at all
When assemble_criterion runs for one of its own criteria
Then dependency_interfaces is an empty mapping, never absent or null
```
