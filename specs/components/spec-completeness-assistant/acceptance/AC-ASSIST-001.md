# AC-ASSIST-001

Covers: R-ASSIST-001
Kind: generated-test

```gherkin
Given a repo_root holding specs/components/foo/requirements/R-FOO-001.md
  and specs/components/bar/requirements/R-BAR-001.md, and stand-ins for
  all four dependencies that each record every call to a log file the
  test controls, the lint stand-in returning one finding with severity
  "fail" and file "specs/components/foo/component.md"
When assist(["R-FOO-001"], repo_root, model="fake-model") runs
Then lint_findings holds that finding unchanged, halted is true,
  predicted_blast_radius is [], criterion_reviews is {},
  completeness_score and completeness_rationale are null,
  redundancy_flags is [], and the log shows no call to
  compute_blast_radius, check or complete

Given the same setup but the fail finding's file is
  "specs/components/bar/component.md"
When assist(["R-FOO-001"], repo_root) runs
Then lint_findings holds that finding, halted is false, and the log
  shows compute_blast_radius called
```
