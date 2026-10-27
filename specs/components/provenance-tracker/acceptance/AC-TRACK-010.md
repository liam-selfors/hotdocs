# AC-TRACK-010

Covers: R-TRACK-010
Kind: generated-test

```gherkin
Given every component in scope is a provenance hit with a passing
  verification_report and no blocking scan, and every intersecting
  capability is a provenance hit with a passing CapabilityScenarioReport
When check_readiness is called
Then ready is true and not_ready_reasons is empty

Given every component passes but one intersecting capability's
  provenance check is a miss
When check_readiness is called
Then ready is false and not_ready_reasons names that capability,
  despite every component passing
```
