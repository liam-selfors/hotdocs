# AC-ASSIST-006

Covers: R-ASSIST-006
Kind: generated-test

```gherkin
Given a repo_root whose specs/components/ holds a fixture component
  whose depends_on does not include comp-spec-completeness-assistant,
  with stand-ins for all four dependencies, lint returning no findings,
  a blast radius of that component, and a check whose to_dict() is {}
When assist(["comp-<that component's slug>"], repo_root) runs with no
  model
Then it returns a CompletenessReport normally rather than raising, and
  the report's public members are exactly its eight fields and
  to_dict()
```
