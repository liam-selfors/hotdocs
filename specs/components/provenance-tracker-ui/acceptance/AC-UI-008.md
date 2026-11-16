# AC-UI-008

Covers: R-UI-008
Kind: generated-test

```gherkin
Given comp-foo is a hit with verification_report.overall "fail", two
  AttemptRecord files under .hotdocs/attempts/comp-foo/ with
  attempt_ids "2026-10-01T00:00:00Z-aaaaaa" and
  "2026-10-02T00:00:00Z-bbbbbb", and a faked last_requirement_failures
  returning ["R-FOO-002"] for comp-foo
When render_tracker_ui runs
Then comp-foo's snapshot attempts list both records oldest first and
  its retry_feedback is ["R-FOO-002"]; its node element contains one
  data-attempt-id element per attempt in that order and an element
  with class retry-feedback whose text is exactly
  "--retry-feedback=R-FOO-002"; and a passing component's node
  contains no retry-feedback element
```
