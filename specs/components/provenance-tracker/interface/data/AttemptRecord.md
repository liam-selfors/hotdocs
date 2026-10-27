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

Never mutated once written, append-only — a later, separate
`hotdocs generate` attempt on the same component writes its own new
file, never edits this one.
