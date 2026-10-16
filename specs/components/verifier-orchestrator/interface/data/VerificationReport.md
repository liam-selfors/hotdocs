# `VerificationReport`

```json
{
  "component_id": "comp-foo",
  "criteria": [
    { "id": "AC-FOO-001", "kind": "compiled", "result": "pass" },
    { "id": "AC-FOO-002", "kind": "llm-judge", "result": "skipped", "rationale": null },
    { "id": "AC-FOO-003", "kind": "generated-test", "result": "pass",
      "test_authoring": { "model": "gpt-5", "seed": 0, "prompt_version": "v1", "cache_hit": false } }
  ],
  "interface_drift": false,
  "mutation_score": 0.92,
  "overall": "pass"
}
```

`result` is one of `pass` / `fail` / `skipped` — mirroring `spec-linter`'s
`severity` vocabulary (R-LINT-015's schema addition) rather than inventing a
second one for the same concept. `test_authoring` is present only on
`generated-test` criteria that actually dispatched to `test_author` this
run (absent on a cache hit with no fresh authoring call, and absent on
every other `kind`) — it's how `test-author`'s own provenance (model, seed,
prompt version) reaches `provenance-writer` without that component needing
a direct dependency on `test-author`: it rides along inside this report,
the same way `llm-judge` rationale already does.
