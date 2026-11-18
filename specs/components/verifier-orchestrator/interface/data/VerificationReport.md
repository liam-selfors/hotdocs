# `VerificationReport`

```json
{
  "component_id": "comp-foo",
  "criteria": [
    { "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass" },
    { "id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "llm-judge", "result": "skipped", "rationale": null },
    { "id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "generated-test", "result": "pass",
      "test_authoring": { "model": "gpt-5", "seed": 0, "prompt_version": "v1", "cache_hit": false } }
  ],
  "requirement_results": { "R-FOO-001": "pass", "R-FOO-002": "fail", "R-FOO-003": "pass" },
  "interface_drift": false,
  "mutation_score": 0.92,
  "mutation_error": null,
  "overall": "pass"
}
```

`mutation_score` is `null` for a sealed component (`R-VERIFY-017`) and
when `mutation_error`, a failed baseline's message
(`specs/architecture/mutation-runs.md`), is set.

`result` is `pass`, `fail` or `skipped`. `test_authoring` appears only
on a `generated-test` criterion that called `test_author` this run,
carrying its provenance to `provenance-writer`.

`covers` (R-VERIFY-011) is each criterion's own `Covers:` value.
`requirement_results` (R-VERIFY-011) projects `criteria` onto `R-id`s via
`covers`: `pass` only if every covering criterion is `pass`, `fail`
otherwise (a `skipped` `llm-judge` criterion counts as `fail` here). It is
**boolean-only**: nothing in it discloses what a test checked.

A `skipped` finding never fails `overall` (R-VERIFY-005), so in the
example `R-FOO-002` is `fail` while `overall` is `pass`.

**`failure_detail`** (R-VERIFY-012) — present only on a `compiled` or
`generated-test` criterion whose `result` is `fail`:

```json
{ "id": "AC-FOO-004", "covers": "R-FOO-004", "kind": "compiled", "result": "fail",
  "failure_detail": { "message": "result.foo equals 5 failed", "expected": 5, "actual": 3 } }
```

**`failure_origin`** (R-VERIFY-019) — present exactly on a `compiled` or
`generated-test` criterion whose `result` is `fail`: `"test"` when no
test could run for it (none authored, or authoring failed),
`"implementation"` when a test ran and failed. A retry attends only to
`"implementation"` failures.
