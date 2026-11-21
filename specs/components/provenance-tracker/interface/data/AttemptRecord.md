# `AttemptRecord`

```json
{
  "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
  "component_id": "comp-foo",
  "timestamp": "2026-10-25T14:32:01Z",
  "spec_bundle_hash": "sha256:...",
  "generation": { "...": "a GenerationResult" },
  "verification": { "...": "a VerificationReport, null if generation itself failed" }
}
```

One file per attempt, under `.hotdocs/attempts/<component_id>/`,
`attempt_id`-prefixed for chronological glob ordering. `verification`
is `null` exactly when `generation.model_call_error` is populated (no
candidate was ever produced to verify) — the same mutually-exclusive
relationship `ComponentPipelineResult` already has between
`model_call_error` and `verification`, preserved here at the
per-attempt level.

**What `last_requirement_failures` reads of `verification`** (`D95`,
`R-TRACK-008`), stated here since this component never depends on
`verifier-orchestrator`: `requirement_results`, a flat JSON object
mapping each `R-id` string to `"pass"` or `"fail"`, such as
`{"R-FOO-001": "pass", "R-FOO-002": "fail"}`; and `criteria`, a list of
objects each with `covers` (one `R-id`), `result` (`"pass"`, `"fail"` or
`"skipped"`) and, on a failed one, `failure_origin` (`"test"`,
`"environment"` or `"implementation"`; absent means `"implementation"`).

Never mutated once written, append-only — a later, separate
`hotdocs generate` attempt on the same component writes its own new
file, never edits this one.

**The `AttemptRecord` `write_attempt_record` returns in memory carries
`generation`/`verification` in exactly this same JSON-equivalent plain
form** (`D100`) — a dict matching this document's own shape precisely,
never the original caller-supplied `GenerationResult`/`VerificationReport`
object echoed back by reference. A caller needing the original object
already has it, having passed it in; this field exists to describe
what was recorded, not to hand back what was received.
