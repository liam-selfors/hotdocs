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
  "overall": "pass"
}
```

`mutation_score` is `null` for a sealed component (`R-VERIFY-017`).

`result` is one of `pass` / `fail` / `skipped`, `spec-linter`'s
`severity` vocabulary. `test_authoring` is present only on
`generated-test` criteria that actually dispatched to `test_author` this
run (absent on a cache hit with no fresh authoring call, and absent on
every other `kind`): it carries `test-author`'s provenance to
`provenance-writer` inside this report, as `rationale` does for
`llm-judge`.

`covers` (R-VERIFY-011) is the same `Covers:` value every criterion already
carries in its own file — exposed here so `requirement_results` is
auditable, not just asserted. `requirement_results` (R-VERIFY-011) is the
graph projection of `criteria` onto `R-id`s via `covers`: `pass` only if
every covering criterion is `pass`, `fail` otherwise (a `skipped`
`llm-judge` criterion counts as `fail` for this purpose — "not yet
demonstrated" and "demonstrated wrong" are the same signal here).
Deliberately **boolean-only** — no Gherkin text, no `rationale`, no
expected/actual values — this is the field `generator`'s retry mechanism
(R-GEN-010) consumes, and it must never carry anything that discloses what
a specific test checked.

**This `skipped`-counts-as-`fail` rule is independent of `overall`'s**
(R-VERIFY-005: a `skipped` `llm-judge` finding alone never fails
`overall`): `overall` decides whether to block the merge,
`requirement_results` what a retry should attend to. In the example,
`AC-FOO-002` is `skipped`, giving `R-FOO-002: fail`, while `overall` is
`pass`.

**`failure_detail`** (R-VERIFY-012) — present only on a `compiled` or
`generated-test` criterion whose `result` is `fail`:

```json
{ "id": "AC-FOO-004", "covers": "R-FOO-004", "kind": "compiled", "result": "fail",
  "failure_detail": { "message": "result.foo equals 5 failed", "expected": 5, "actual": 3 } }
```

Mirrors `llm-judge`'s `rationale` one `kind` family over — every `kind`
that can fail now carries its own structured account of why. Exposed
for provenance/review-packet/human consumption only: it never reaches
`requirement_results` (already boolean-only, above) or
`retry_feedback`'s `R-id`-only channel (`R-GEN-012`).
