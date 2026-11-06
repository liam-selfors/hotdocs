# `LicenseScanResult`

```json
{
  "component_id": "comp-foo",
  "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
  "evaluated": true,
  "reason": null,
  "similarity_score": 0.55,
  "block_threshold": 0.70,
  "blocked": false,
  "matches": [
    { "reference_id": "ref-123", "license_family": "gpl-3.0", "risk_tier": "high", "score": 0.55 }
  ],
  "notified": true,
  "notification_delivery_error": null,
  "cache_hit": false
}
```

**`evaluated` and `reason`** (`R-LICENSE-010`): `evaluated` is `true` only
when a usable corpus was compared against. When `false`, `similarity_score`
and `block_threshold` are `null` and `matches` is `[]`, and `reason` is
`"no-reference-corpus"`, `"corpus-unreadable"`, or `"corpus-invalid"`. A
not-evaluated result is a different thing from a clean one, never an
absent-flag clean: any consumer MUST treat `evaluated: false` as "nothing was
checked".

`matches` is non-empty only when `similarity_score` is above a reporting
floor (always populated on a flagged result; may be empty on a clean one).
Each match entry carries its reference's own `license_family` and
`risk_tier`, curated with the reference corpus, not computed here.
`blocked` is `similarity_score >= block_threshold` (confidence only) when
`evaluated` is `true`; when `evaluated` is `false` it is `true` exactly for
`corpus-unreadable` and `corpus-invalid` (`R-LICENSE-011`), `false` for
`no-reference-corpus`.
`notified` is `(blocked) OR (any match's risk_tier == "high")`, **and**
`VAR-COMPLIANCE-WEBHOOK-URL` is configured: deliberately not a function of
`similarity_score` against a second threshold. It reflects whether a
notification was **due**, never whether it was delivered.
`notification_delivery_error` is `{category, message}` or `null`
(`category` one of `network`/`auth`/`timeout`), populated only when
`notified` is `true` and the webhook call failed (`R-LICENSE-003`); it never
affects `blocked`.
