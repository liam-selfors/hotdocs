# `AttemptLoopResult`

```json
{
  "passed": false,
  "stop_reason": "max_attempts",
  "attempts": [
    {"number": 1, "outcome": "verification_failed", "retry_feedback": [],
     "error_category": null, "surface_ok": true, "overall": "fail",
     "failed_requirements": ["R-FOO-002"], "transcript_sha256": null},
    {"number": 2, "outcome": "generation_failed", "retry_feedback": ["R-FOO-002"],
     "error_category": "truncated_response", "surface_ok": null, "overall": null,
     "failed_requirements": [], "transcript_sha256": null}
  ],
  "generation_result": "<the last GenerationResult>",
  "verification_report": "<the last VerificationReport, or null>",
  "surface_report": "<the last SurfaceReport, or null>"
}
```

A dataclass with these fields in this order, with a `to_dict()` giving
the JSON form, each attempt a plain dict with exactly these keys.
`outcome` is one of `passed`, `verification_failed`, `surface_failed`,
`generation_failed`, `refused`. `stop_reason` is `passed`,
`max_attempts`, `not_retried` (an error a new attempt cannot fix) or
`refused`. `failed_requirements` are the ids that attempt contributes
to the next one's feedback.
