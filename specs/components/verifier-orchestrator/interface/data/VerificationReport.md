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
  "assets": [],
  "overall": "pass"
}
```

`mutation_score` is `null` for a sealed component (`R-VERIFY-017`),
when `mutation_error` is set (`specs/architecture/mutation-runs.md`) and
when an environment failed (`R-VERIFY-020`).

`result` is `pass`, `fail` or `skipped`. `test_authoring` appears only
on a `generated-test` criterion that called `test_author` this run.

`covers` is the criterion's own `Covers:` value; `requirement_results`
is R-VERIFY-011's projection. In the example `R-FOO-002` is `fail`
while `overall` is `pass` (R-VERIFY-005).

**`failure_detail`** (R-VERIFY-012), only on a failed `compiled` or
`generated-test` criterion:

```json
{ "id": "AC-FOO-004", "covers": "R-FOO-004", "kind": "compiled", "result": "fail",
  "failure_detail": { "message": "result.foo equals 5 failed", "expected": 5, "actual": 3 } }
```

**`failure_origin`** (R-VERIFY-019), exactly on a failed `compiled` or
`generated-test` criterion: `"test"` when no sound test could run for it,
`"environment"` when a declared kind is unknown or unprovisioned
(`R-VERIFY-020`), `"implementation"` when a test ran and failed. A retry
attends only to `"implementation"` failures.

**`assets`** (R-VERIFY-020), one entry per declared asset in
declaration order, `[]` with none, as
`specs/architecture/asset-kinds.md`'s Provenance bullet states:

```json
{ "kind": "javascript", "path": "static/app.js",
  "definition_sha256": "sha256:<hex>", "adapter_sha256": "sha256:<hex>",
  "versions": { "node": "24.1.0" }, "lockfile_sha256": null }
```
