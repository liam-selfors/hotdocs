# `GenerationResult`

```json
{
  "component_id": "comp-foo",
  "model": "claude-sonnet-5",
  "seed": 0,
  "prompt_version": "v1",
  "cache_hit": false,
  "files": { "spec_linter.py": "<file content>" },
  "model_call_error": null
}
```

`model_call_error` is `null` on success; when non-null (R-GEN-008), `files`
MUST be empty and `cache_hit` MUST be `false` — a failed call never produces
partial output.
