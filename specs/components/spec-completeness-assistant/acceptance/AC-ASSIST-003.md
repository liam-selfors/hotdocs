# AC-ASSIST-003

Covers: R-ASSIST-003
Kind: generated-test

```gherkin
Given a repo_root with a faked spec-linter returning no findings, a
  faked impact-analyzer whose blast radius is exactly comp-foo, a faked
  llm-endpoint, and faked spec-bundle-assembler and generator modules
  that each record every call to a log file the test controls
When assist(changed_ids, repo_root, model="fake-model") runs
Then hint_previews has exactly one key, comp-foo, and the log shows
  assemble called for comp-foo with mode "hint" (never "cold") and
  generate called once with that bundle

Given the same setup
When assist(changed_ids, repo_root) runs with no model
Then hint_previews still has exactly one key, comp-foo, the log shows
  assemble called with mode "hint", and shows no generate call
```
