# AC-ASSIST-001

Covers: R-ASSIST-001
Kind: generated-test

```gherkin
Given a repo_root with faked spec-linter, impact-analyzer,
  spec-bundle-assembler, generator, and llm-endpoint modules, where the
  faked lint returns one finding with severity "fail", and every other
  fake records each call to a log file the test controls
When assist(changed_ids, repo_root, model="fake-model") runs
Then lint_findings holds that finding unchanged, predicted_blast_radius
  is [], hint_previews is {}, completeness_score and
  completeness_rationale are null, redundancy_flags is [], and the log
  shows no call to impact-analyzer, generator, or llm-endpoint

Given the same setup but the faked lint returns only a "warn" finding
When assist runs
Then it proceeds past linting and the log shows impact-analyzer called
```
