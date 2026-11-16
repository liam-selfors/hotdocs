# AC-PROBE-001

Covers: R-PROBE-001
Kind: generated-test

```gherkin
Given the test source "def test_a(:\n    pass\n"
When probe(source, {}, "slugify") is called
Then ok is False, findings is exactly one finding of kind "syntax_error",
  severity "error" and line 1, and tests_run and tests_reached are 0
```
