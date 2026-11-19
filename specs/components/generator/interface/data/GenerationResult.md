# `GenerationResult`

```json
{
  "component_id": "comp-foo",
  "spec_bundle_hash": "sha256:...",
  "model": "claude-sonnet-5",
  "prompt_version": "v12",
  "cache_hit": false,
  "files": { "foo.py": "<file content>" },
  "model_call_error": null,
  "refused": null,
  "retry_feedback": ["R-FOO-003"],
  "mode": "single",
  "transcript_sha256": null,
  "turns": 1,
  "tool_calls": 0,
  "isolation": null
}
```

`generate` returns a `GenerationResult` dataclass with these fields, in
this order. `retry_feedback` echoes the caller's (`null` if none). `generate` always returns `mode`
`"single"`, `transcript_sha256` `null`, `turns` `1`, `tool_calls` `0`
and `isolation` `null` (a cache hit included); another generation mode
fills them with its own values, `isolation` naming how code the model
ran was contained.

Exactly one of `files` (non-empty), `model_call_error`, or `refused` is
populated on any result (`files` is `{}` when it is not), and
`cache_hit` is `false` whenever either of the other two is set.
`model_call_error` (R-GEN-008, R-GEN-021), a dict
`{"category": ..., "message": ...}`, means no usable candidate
(`environment` before any model call); `refused`
(R-GEN-009), the reason, means no model call was attempted.
