# AC-GATE-012

Covers: R-GATE-012
Kind: generated-test

```gherkin
Given the faked dependencies with check_provenance returning
  {"hit": false, "reason": "spec changed"}, a run_attempts stand-in that
  records whether verification/foo/generated-test/test_ac_foo_001.py
  exists when it is called, a
  specs/components/foo/acceptance/AC-FOO-001.md holding the line
  "Kind: generated-test", and that test file existing
When main(["generate", "comp-foo", "--model=m", "--reauthor=AC-FOO-001",
  "--repo-root=<repo_root>"]) runs
Then the run_attempts stand-in recorded that the file did not exist

Given the same files and check_provenance returning a hit,
  {"hit": true, "reason": null} with a passing verification_report
When main runs the same arguments
Then the test file still exists

Given --reauthor=AC-FOO-009, which has no acceptance file
When main runs generate for comp-foo with --model=m
Then it returns 2, its first stderr line starts "usage error: " and
  contains "AC-FOO-009 is not a generated-test criterion of comp-foo",
  and no stand-in recorded any call
```
