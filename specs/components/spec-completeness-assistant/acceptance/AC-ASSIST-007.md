# AC-ASSIST-007

Covers: R-ASSIST-007
Kind: generated-test

```gherkin
Given a repo_root with a faked spec-linter returning one "warn"
  finding, a faked impact-analyzer whose blast radius is comp-foo,
  faked spec-bundle-assembler and generator modules, and a faked
  llm-endpoint that records every call to a log file the test controls
When assist(changed_ids, repo_root) runs with no model
Then lint_findings holds the warn finding, predicted_blast_radius is
  ["comp-foo"], hint_previews has a comp-foo entry, degraded is true,
  completeness_score and completeness_rationale are null,
  redundancy_flags is [], and the log shows no llm-endpoint call
```
