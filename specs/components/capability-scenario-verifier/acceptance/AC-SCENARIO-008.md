# AC-SCENARIO-008

Covers: R-SCENARIO-005
Kind: generated-test

```gherkin
Given a generated-test scenario whose fake test_author returns a test
  "def test_x():\n    assert False\n"
When run_capability_scenarios runs
Then that scenario's result is "fail", overall is "fail", and the test
  file exists on disk at the returned path

Given a returned path of "../escape.py", an absolute path inside a
  separate temporary directory the test created (never a fixed path
  such as /tmp/escape.py, which other runs would share), or
  "notverification/x.py"
When run_capability_scenarios runs
Then the scenario is "fail" and nothing was written at that path

Given a fake test_author returning a model_call_error, or no file
When run_capability_scenarios runs
Then the scenario is "fail"

Given a realizing component with code gen/foo/foo_mod.py defining
  value() returning 7, and a returned test that imports foo_mod and
  asserts value() == 7
When run_capability_scenarios runs
Then the scenario is "pass", so the test ran with that component's code
  directory on PYTHONPATH
```
