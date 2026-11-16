# `GenerationResult`

```json
{
  "component_id": "comp-foo",
  "spec_bundle_hash": "sha256:...",
  "model": "claude-sonnet-5",
  "prompt_version": "v11",
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
this order. `spec_bundle_hash` (`R-GEN-017`) echoes
`bundle.spec_bundle_hash`; `retry_feedback` echoes what the caller
supplied (`null` if nothing was). `generate` always returns `mode`
`"single"`, `transcript_sha256` `null`, `turns` `1`, `tool_calls` `0`
and `isolation` `null` (a cache hit included); another generation mode
fills them with its own values, `isolation` naming how code the model
ran was contained.

Exactly one of `files` (non-empty), `model_call_error`, or `refused` is
populated on any result (`files` is `{}` when it is not), and
`cache_hit` is `false` whenever either of the other two is set.
`model_call_error` (R-GEN-008, R-GEN-021), a dict
`{"category": ..., "message": ...}`, means a model call was attempted
and produced no usable candidate (a mock `llm_backend` reply that
`R-GEN-021` rejects gives one; a test MAY also build a result by
keyword); `refused`
(R-GEN-009) means no model call was attempted at all, with a short
reason such as `"sealed-component"` or `"pinned-override"`.
