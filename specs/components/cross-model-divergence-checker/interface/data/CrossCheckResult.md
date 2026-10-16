# `CrossCheckResult`

```json
{
  "component_id": "comp-foo",
  "second_model": "gpt-5",
  "mode": "divergence",
  "different_vendor": true,
  "second_candidate_verification": { "...": "a VerificationReport, see verifier-orchestrator/interface.md" },
  "diverged": false,
  "divergence_detail": null
}
```

`diverged` is `null` in `standby-only` mode (R-XMODEL-007 never runs the
comparison); `false`/`true` in `divergence` mode. `divergence_detail` names
the specific criterion(s) involved when `diverged` is `true` — never just a
boolean with no actionable detail (R-XMODEL-005).
