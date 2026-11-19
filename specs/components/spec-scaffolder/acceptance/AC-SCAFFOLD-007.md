# AC-SCAFFOLD-007

Covers: R-SCAFFOLD-007
Kind: generated-test

```gherkin
Given a repo_root with a specs/ directory whose specs/decisions/ holds D4.md
When new_kind(repo_root, "yaml", owners=["team-a"],
  realizes=["P-DATA"]) is called
Then it returns [specs/architecture/asset-kind-yaml.md,
  specs/components/kind-yaml, specs/decisions/D5.md], each under
  repo_root; the definition is exactly the R-SCAFFOLD-007 layout with
  kind yaml, title "yaml" and owners [team-a], so its first
  heading is "# Asset kind `yaml`" and its "## " lines are, in
  order, Layout, Environment, Surface, Running criteria, Strength check,
  Test author guidance and Generator guidance; and D5.md is exactly the
  R-SCAFFOLD-002 layout with id D5, title "Asset kind yaml",
  owners [team-a] and neither a builds_on nor a supersedes line

Given a repo_root with a specs/ directory
When new_kind(repo_root, "sql", title="SQL") is called
Then the definition's title line is "title: Asset kind SQL", its owners
  line is "owners: [unassigned]", and its first heading is
  "# Asset kind `sql`"

Given the repo_root after the first scenario
When new_kind(repo_root, "yaml") is called again
Then it raises FileExistsError and no D6.md appears

Given a repo_root with a specs/ directory holding only
  specs/components/kind-sql/
When new_kind(repo_root, "sql") is called
Then it raises FileExistsError, and neither specs/architecture/ nor
  specs/decisions/ exists afterwards

Given a repo_root with a specs/ directory
When new_kind is called with each of "python", "Data_Schema", "9x",
  "sql-", "a--b" and "data-schema"
Then each raises ValueError, and specs/ holds nothing new afterwards
```
