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

`result` is one of `pass` / `fail` / `skipped` — mirroring `spec-linter`'s
`severity` vocabulary (R-LINT-015's schema addition) rather than inventing a
second one for the same concept. `test_authoring` is present only on
`generated-test` criteria that actually dispatched to `test_author` this
run (absent on a cache hit with no fresh authoring call, and absent on
every other `kind`) — it's how `test-author`'s own provenance (model, seed,
prompt version) reaches `provenance-writer` without that component needing
a direct dependency on `test-author`: it rides along inside this report,
the same way `llm-judge` rationale already does.

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

**This `skipped`-counts-as-`fail` rule is deliberately stricter than, and
independent from, `overall`'s rule** (R-VERIFY-005: a `skipped` `llm-judge`
finding alone never fails `overall`). The two fields answer different
questions: `overall` decides whether to *block the merge*, where "not
evaluated" rightly isn't treated as "violated." `requirement_results`
decides what's worth a *retry's attention*, where "not yet demonstrated"
is just as retry-worthy as "demonstrated wrong" — both mean this
requirement isn't verified yet. The worked example above shows exactly
this: `AC-FOO-002` is `skipped`, contributing `R-FOO-002: fail` to
`requirement_results`, while `overall` is still `pass`.
