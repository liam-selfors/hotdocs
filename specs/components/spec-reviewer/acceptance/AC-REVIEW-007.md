# AC-REVIEW-007

Covers: R-REVIEW-007
Kind: generated-test

```gherkin
Given a lint-clean synthetic corpus whose AC-FOO-001 mentions `--fast`,
  which nothing else in the bundle mentions
When main(["comp-foo", "--format=json", "--repo-root=<repo_root>"]) is
  called
Then it returns 0 and stdout parses as JSON whose findings has one entry
  with token "--fast"

Given the same corpus
When main(["comp-foo", "--strict", "--repo-root", "<repo_root>"]) is
  called
Then it returns 1, and stdout's last line is
  "1 criteria checked, 1 findings, 0 gaps"

Given the same corpus
When main is called with ["AC-FOO-404", "--repo-root=<repo_root>"],
  with ["comp-foo", "--format=bogus"], with ["comp-foo", "--model"], and
  with []
Then each returns 2, stderr's first line starts "usage error: ", and
  no traceback is printed
```
