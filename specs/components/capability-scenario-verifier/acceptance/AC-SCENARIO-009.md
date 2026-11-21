# AC-SCENARIO-009

Covers: R-SCENARIO-005
Kind: generated-test

This criterion supplies a fake `criterion_compiler` module at
`<repo_root>/pipeline/criterion-compiler/criterion_compiler.py`: a class
`ParsedCriterion` accepting `criterion_id`, `covers`, `kind`, `gherkin`,
and `file` keywords, and `compile_criterion(parsed, surface=None)`
returning what each scenario below says.

```gherkin
Given a compiled scenario CS-X-001 and a fake compile_criterion
  returning {"status": "compiled", "source": "def test_x():\n    assert
  True\n"}
When run_capability_scenarios runs
Then the source was written to verification/capabilities/P-X/compiled/
  test_cs_x_001.py, was run, and the scenario is "pass"

Given the same, but the source is "def test_x():\n    assert False\n"
When run_capability_scenarios runs
Then that file exists and the scenario is "fail"

Given the fake returning {"status": "error", "message": "bad step"}
When run_capability_scenarios runs
Then the scenario is "fail" and no file exists under
  verification/capabilities/P-X/compiled/

Given the real criterion-compiler, copied from <live> as
  specs/architecture/capability-scenario-fixtures.md says, and
  a compiled scenario with gherkin "Given a x is 1\nThen x equals 1"
  (it compiles, but its test asserts on a result no step defines)
When run_capability_scenarios runs
Then the scenario is "fail", never "pass": compiling alone is not a pass
```
