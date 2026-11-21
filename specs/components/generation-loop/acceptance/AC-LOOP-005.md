# AC-LOOP-005

Covers: R-LOOP-005
Kind: generated-test

```gherkin
Given a generate stand-in returning, in order, a truncated_response error
  and then files with transcript_sha256 "sha256:t2", a passing
  check_surface, a passing verify, and an on_attempt callback recording
  its three arguments
When run_attempts(..., on_attempt=callback) is called
Then the callback was called twice; its first call's report argument is
  None and its second's is the verify result; the attempts are numbered
  1 and 2 with transcript_sha256 None and "sha256:t2"; and the result's
  generation_result is the second generation result and to_dict()
  gives a dict whose "attempts" entries each have exactly the keys
  number, outcome, retry_feedback, error_category, surface_ok, overall,
  failed_requirements and transcript_sha256
```
