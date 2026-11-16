# AC-ASSIST-002

Covers: R-ASSIST-002
Kind: generated-test

```gherkin
Given a repo_root with a faked spec-linter returning no findings, a
  faked impact-analyzer whose blast radius for the draft change is
  exactly comp-alpha and comp-beta, and faked spec-bundle-assembler and
  generator modules
When assist(changed_ids, repo_root) runs
Then predicted_blast_radius lists exactly comp-alpha and comp-beta
```
