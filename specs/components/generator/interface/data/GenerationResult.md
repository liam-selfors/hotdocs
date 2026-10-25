# `GenerationResult`

```json
{
  "component_id": "comp-foo",
  "model": "claude-sonnet-5",
  "prompt_version": "v1",
  "cache_hit": false,
  "files": { "spec_linter.py": "<file content>" },
  "model_call_error": null,
  "refused": null,
  "retry_feedback": ["R-FOO-003"]
}
```

No `seed`/`sample_index` fields — `D31` retired the best-of-k retry loop
that was their only reason to exist, and `generator` is still called at
most once per component per merge attempt, so there is no "which sample
won" left to record. `retry_feedback` itself came back under `D33`:
`D31` mistakenly removed it along with the automatic loop, but it was
never only useful for feeding that loop — it's restored here as a plain
echo of whatever a caller supplied (`null` if nothing was), for the same
audit reason it always existed: an auditor reconstructing why a given
attempt looks the way it does needs to know whether it was informed or
blind.

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
