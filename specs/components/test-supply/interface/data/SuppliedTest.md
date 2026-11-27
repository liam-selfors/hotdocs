# `SuppliedTest`

```json
{
  "criterion_id": "AC-FOO-003",
  "path": "/tmp/tmpq1/test_ac_foo_003.py",
  "authored": true,
  "test_authoring": {"model": "claude-opus-5-5", "seed": 0, "prompt_version": "v4", "cache_hit": false},
  "failure_origin": null,
  "failure_message": null
}
```

A dataclass with these fields and `to_dict()`. `path` is the file to
run: the committed file, or the authored one in a temporary directory;
`null` exactly when `failure_origin` is `"test"`, with
`failure_message` saying why. `authored` is `true` exactly when
`test_author` was called, whether or not it returned a sound test, so
it is `true` exactly when `test_authoring` is not `null`. `test_authoring` is the last
`test_author` call's `model`, `seed`, `prompt_version` and `cache_hit`,
`null` when it was not called.
