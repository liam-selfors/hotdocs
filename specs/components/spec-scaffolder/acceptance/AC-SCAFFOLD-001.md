# AC-SCAFFOLD-001

Covers: R-SCAFFOLD-001
Kind: generated-test

```gherkin
Given a repo_root with no specs/decisions/ directory
When next_decision_id(repo_root) is called
Then it returns "D1"

Given a repo_root whose specs/decisions/ holds D1.md, D7.md, D12.md,
  README.md and D3-notes.md
When next_decision_id(repo_root) is called
Then it returns "D13"
```
