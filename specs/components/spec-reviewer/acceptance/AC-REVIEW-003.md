# AC-REVIEW-003

Covers: R-REVIEW-003
Kind: generated-test

```gherkin
Given a lint-clean synthetic corpus whose AC-FOO-001 Gherkin block reads
  "Given x = `7` and `--slow`", then "When foo(x) is called with `--opt=<v>`",
  then "Then it returns `4`, and `--fast` and `foo` are honored,", then an
  indented "  and `--fast` again", and whose requirement and interface mention
  foo, 4 and --opt= but never --fast, --slow or 7
When check(["AC-FOO-001"], repo_root) is called with no model
Then findings holds exactly one finding, with criterion_id "AC-FOO-001",
  kind "invisible_reference", token "--fast" and message
  "`--fast` appears in AC-FOO-001 but not in what its test author sees";
  writable is {"AC-FOO-001": None}; gaps is empty; and degraded is true
```
