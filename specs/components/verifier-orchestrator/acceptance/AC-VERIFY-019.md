# AC-VERIFY-019

Covers: R-VERIFY-017
Kind: generated-test

```gherkin
Given a sealed component foo (frontmatter "sealed: true" and
  "source_path: pipeline/foo/") whose code is pipeline/foo/foo.py
  defining do_the_thing(x) as documented in its interface/library.md,
  with nothing under gen/foo/, two generated-test criteria AC-FOO-001
  and AC-FOO-002, and verification/foo/test_foo.py holding
  test_ac_foo_001_returns_value and test_ac_foo_001_other, both passing,
  plus test_ac_foo_002_fails, failing
When verify("comp-foo", repo_root) runs with no test_author or judge
Then AC-FOO-001 is pass, AC-FOO-002 is fail with a failure_detail,
  interface_drift is false, mutation_score is null, and overall is fail

Given AC-FOO-002's test is fixed to pass
When verify runs
Then overall is pass

Given a third criterion AC-FOO-003 with no matching test function
When verify runs
Then AC-FOO-003 is fail with failure_detail.message
  "no characterization test", and a test named test_ac_foo_0031_x does
  not count for it

Given pipeline/foo/.sealed-provenance.json and pipeline/foo/__pycache__/
  are added
When verify runs
Then the results are unchanged

Given the pipeline/foo/ directory is removed
When verify runs
Then overall is fail
```
