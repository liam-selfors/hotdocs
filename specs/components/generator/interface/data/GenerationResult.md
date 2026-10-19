# `GenerationResult`

```json
{
  "component_id": "comp-foo",
  "model": "claude-sonnet-5",
  "seed": 0,
  "prompt_version": "v1",
  "cache_hit": false,
  "files": { "spec_linter.py": "<file content>" },
  "model_call_error": null,
  "refused": null,
  "retry_feedback": ["R-FOO-003"]
}
```

`retry_feedback` (R-GEN-010) echoes exactly what was passed into this
specific call — `null` on a sequence's first attempt, an `R-id` list on a
later one. Recorded for the same reason `sample_index` already is: an
auditor reconstructing why a given attempt looks the way it does needs to
know not just *which* sample won, but whether it was informed by a prior
failure or a blind attempt.

Exactly one of `files` (non-empty), `model_call_error`, or `refused` is
populated on any given result — never more than one, and `cache_hit` is
`false` whenever either `model_call_error` or `refused` is set (a failed or
refused call never produces partial or cached output). `model_call_error`
is a real API failure (R-GEN-008) — a model call was attempted. `refused`
(R-GEN-009) is the opposite: it means **no model call was attempted at
all** — the target was a sealed component's `source_path` or a pinned
`.overrides.json` file, caught by the precondition check before any cost
was incurred. The two MUST NOT be conflated: one implies "the model tried
and failed," the other implies "generation never tried, by design."
`refused`'s value is a short machine-readable reason string, e.g.
`"sealed-component"` or `"pinned-override"`.
