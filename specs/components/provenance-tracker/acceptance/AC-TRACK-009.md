# AC-TRACK-009

Covers: R-TRACK-009
Kind: generated-test

```gherkin
Given changed_ids naming one changed component, impact-analyzer
  reporting a blast radius of two components, and
  component-gate-runner's run_component_gates reporting a passing
  result for one and a missing/failing one for the other
When check_readiness is called with those changed_ids
Then the report's scope is blast-radius, its components map has
  exactly those two entries, and the failing one is named in
  not_ready_reasons

Given no changed_ids
When check_readiness is called
Then every component under specs/components/ is checked via
  run_component_gates, and the report's scope is whole-corpus

Given changed_ids naming exactly one component and a retry_feedback
  list
When check_readiness is called with both
Then that component's run_component_gates call receives
  retry_feedback; given changed_ids naming more than one component (or
  none) and a retry_feedback list, check_readiness raises a usage error
  instead of applying it to any of them

Given a blast radius containing comp-bar and comp-foo, where comp-foo
  depends_on comp-bar
When check_readiness sequences their run_component_gates calls
Then comp-bar's call completes before comp-foo's begins
```
