# AC-SCAFFOLD-002

Covers: R-SCAFFOLD-002
Kind: generated-test

```gherkin
Given a repo_root whose specs/decisions/ holds D4.md
When new_decision(repo_root, "Slugs are ASCII", owners=["team-a"],
  builds_on=["D4"]) is called
Then it returns the path specs/decisions/D5.md under repo_root, and that
  file's text is exactly the R-SCAFFOLD-002 layout with id D5, title
  "Slugs are ASCII", owners [team-a], the line "builds_on: [D4]" and no
  supersedes line

Given the same repo_root
When new_decision(repo_root, "No owners") is called
Then the written file's owners line is "owners: [unassigned]" and it has
  neither a builds_on nor a supersedes line

Given the same repo_root
When new_decision(repo_root, "x", builds_on=["D99"]) is called, and
  separately new_decision(repo_root, "") is called
Then each raises ValueError and no new file appears under specs/decisions/
```
