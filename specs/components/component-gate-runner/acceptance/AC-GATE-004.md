# AC-GATE-004

Covers: R-GATE-004
Kind: generated-test

```gherkin
Given a provenance miss and a faked run_attempts returning passed false
  whose last attempt's outcome is <outcome>
When run_component_gates is called
Then blocked is true and block_reason is <reason>

Examples:
  | outcome             | reason                 |
  | generation_failed   | model_call_error       |
  | surface_failed      | surface_check_failed   |
  | verification_failed | verification_failed    |
  | refused             | refused                |
```
