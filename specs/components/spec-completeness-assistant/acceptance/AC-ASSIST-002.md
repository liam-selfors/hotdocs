# AC-ASSIST-002

Covers: R-ASSIST-002
Kind: generated-test

```gherkin
Given a repo_root with stand-ins for all four dependencies, lint
  returning no findings and the blast radius for the draft change being
  exactly comp-alpha and comp-beta
When assist(["R-ALPHA-001"], repo_root) runs
Then predicted_blast_radius lists exactly comp-alpha and comp-beta
```
