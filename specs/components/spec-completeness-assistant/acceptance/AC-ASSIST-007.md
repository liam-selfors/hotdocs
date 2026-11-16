# AC-ASSIST-007

Covers: R-ASSIST-007
Kind: generated-test

```gherkin
Given a repo_root with stand-ins for all four dependencies that record
  every call, and its arguments, to a log file the test controls: lint
  returning one "warn" finding, a blast radius of comp-foo, and a check
  returning an object whose to_dict() is {"findings": []}
When assist(["R-FOO-001"], repo_root) runs with no model
Then lint_findings holds the warn finding, predicted_blast_radius is
  ["comp-foo"], criterion_reviews has a comp-foo entry, degraded is
  true, completeness_score and completeness_rationale are null,
  redundancy_flags is [], lint was called with judge None, and the log
  shows no complete and no glossary_judge call
```
