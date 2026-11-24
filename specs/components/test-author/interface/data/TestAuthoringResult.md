# `TestAuthoringResult`

```json
{
  "component_id": "comp-foo",
  "criterion_id": "AC-FOO-003",
  "model": "claude-sonnet-5",
  "seed": 0,
  "prompt_version": "v1",
  "cache_hit": false,
  "file": { "path": "verification/foo/generated-test/test_ac_foo_003.py", "content": "<test code>" },
  "model_call_error": null,
  "repair_attempts": 0,
  "probe_findings": []
}
```

`cache_hit` is always `false` (`R-AUTHOR-030`). `probe_findings` (`R-AUTHOR-027`) entries are `test-probe`'s finding dicts.
