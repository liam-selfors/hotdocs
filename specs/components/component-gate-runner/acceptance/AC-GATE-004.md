# AC-GATE-004

Covers: R-GATE-004
Kind: generated-test

```gherkin
Given a provenance miss and a faked run_attempts returning passed false
  whose last attempt's outcome is <outcome>, with that attempt's
  verification_report, when one ran, having AC-FOO-001 "fail" with
  failure_origin "implementation"
When run_component_gates is called
Then blocked is true and block_reason is <reason>

Examples:
  | outcome             | reason                 |
  | generation_failed   | model_call_error       |
  | surface_failed      | surface_check_failed   |
  | verification_failed | verification_failed    |
  | refused             | refused                |

Given a provenance miss and a faked run_attempts returning passed false
  whose last attempt's outcome is verification_failed, with its
  verification_report's AC-FOO-001 "fail" with failure_origin "test"
  and AC-FOO-002 "pass"
When run_component_gates is called
Then blocked is true and block_reason is "test_authoring_failed"
```
