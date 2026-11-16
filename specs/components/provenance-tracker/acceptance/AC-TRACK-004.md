# AC-TRACK-004

Covers: R-TRACK-004
Kind: generated-test

```gherkin
Given component-gate-runner calling write_attempt_record with a
  component_id, a GenerationResult, a VerificationReport (or null), and
  a spec_bundle_hash as plain parameters
When write_attempt_record runs
Then it writes the AttemptRecord from those parameters directly,
  never from a reference to component-gate-runner's own
  ComponentPipelineResult type — confirmed by this component's own
  depends_on list specifically excluding comp-component-gate-runner
  (this component may still list other real dependencies; the only
  claim under test is that comp-component-gate-runner itself is not
  one of them)
```
