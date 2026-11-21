# AC-SCAFFOLD-003

Covers: R-SCAFFOLD-003
Kind: generated-test

```gherkin
Given a repo_root with a ratified D2.md (status: ratified) and a draft
  D3.md written by new_decision(repo_root, "Replace two",
  supersedes="D2")
When ratify(repo_root, "D3") is called
Then it returns [the path of D3.md, the path of D2.md]; D3.md has the line
  "status: ratified" and, as its last frontmatter line,
  "last_ratified_commit: PENDING-COMMIT"; D2.md has the line
  "status: deprecated"; and every other line of both files is unchanged

Given that same repo_root after the ratify
When ratify(repo_root, "D3") is called again, and separately
  ratify(repo_root, "D40") is called
Then each raises LookupError and no file changes
```
