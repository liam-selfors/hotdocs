# `GenerationResult`

```json
{
  "component_id": "comp-foo",
  "spec_bundle_hash": "sha256:...",
  "model": "claude-sonnet-5",
  "prompt_version": "v1",
  "cache_hit": false,
  "files": { "spec_linter.py": "<file content>" },
  "model_call_error": null,
  "refused": null,
  "retry_feedback": ["R-FOO-003"]
}
```

`spec_bundle_hash` (`R-GEN-017`, `D83`) echoes `bundle.spec_bundle_hash`.

No `seed`/`sample_index` fields (`D31` retired best-of-k, no "which
sample won" left to record). `retry_feedback` (`D33`) is a plain echo
of whatever a caller supplied (`null` if nothing was) — an auditor
needs to know whether an attempt was informed or blind.

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
