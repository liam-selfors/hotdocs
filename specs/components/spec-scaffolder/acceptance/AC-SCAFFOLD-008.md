# AC-SCAFFOLD-008

Covers: R-SCAFFOLD-008
Kind: generated-test

```gherkin
Given two empty repo_roots A and B, each with a specs/ directory
When new_kind(A, "yaml", title="YAML", realizes=["P-DATA"])
  is called, and new_component(B, "kind-yaml",
  title="Kind YAML", realizes=["P-DATA"]) is called
Then A's specs/components/kind-yaml/ holds every file B's does,
  each with the same bytes, and exactly three more:
  interface/library.md, requirements/R-KIND-YAML-001.md and
  acceptance/AC-KIND-YAML-001.md, each exactly the R-SCAFFOLD-008
  layout with kind yaml, module yaml and KIND YAML;
  so library.md has the lines
  "One module file, `kind_yaml.py`, never a package.",
  "GATE_VERSION: str   # \"kind-yaml@0.1.0\"" and
  "Implements: `specs/architecture/asset-kinds.md`, `specs/architecture/asset-kind-yaml.md`",
  and the criterion's lines 3 and 4 are
  "Covers: R-KIND-YAML-001" and "Kind: generated-test"

Given a repo_root with a specs/ directory
When new_kind(repo_root, "sql") is called
Then specs/components/kind-sql/component.md has the lines
  "id: comp-kind-sql", "title: Kind sql", "owners: [unassigned]" and
  "realizes: []", and the requirement file is
  requirements/R-KIND-SQL-001.md, whose first line is "# R-KIND-SQL-001"
```
