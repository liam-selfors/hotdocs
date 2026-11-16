# AC-AUTHOR-027

Covers: R-AUTHOR-027
Kind: generated-test

```gherkin
Given a mock model recording each prompt and replying, in call order,
  with marked files "BAD1", "BAD2" and "GOOD", and a test-probe stand-in
  returning ok False with one error finding {"kind": "undefined_name",
  "severity": "error", "line": 3, "message": "undefined name 'x'"} for
  any source other than "GOOD", and ok True with no finding for "GOOD"
When author_test is called
Then the model was called three times, the second prompt contains
  "BAD1" and "undefined_name (line 3): undefined name 'x'", the result
  has no model_call_error, repair_attempts is 2, probe_findings is [],
  and the written file's content after its first line is "GOOD"

Given the same stand-in and a mock model replying "BAD1", "BAD2", "BAD3"
When author_test is called
Then the model was called three times, the result has model_call_error
  with category "test_probe_failed", a null file, repair_attempts 2,
  probe_findings holding that finding, and nothing is written or cached
```
