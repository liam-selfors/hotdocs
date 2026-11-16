# AC-SCENARIO-002

Covers: R-SCENARIO-002
Kind: generated-test

```gherkin
Given the blast radius is {comp-foo, comp-bar}, only comp-foo's
  component.md declares realizes: [P-ZERO-EDIT], and a second
  capability P-UNRELATED is realized by neither
When run_capability_scenarios runs
Then the report's only key is P-ZERO-EDIT

Given comp-baz is sealed: true with source_path pipeline/baz/, realizes
  P-SEALED, and has its code under pipeline/baz/ and none under gen/baz/
When P-SEALED's scenario test imports a module from pipeline/baz/
Then it passes, since the sealed component's code directory is its
  source_path
```
