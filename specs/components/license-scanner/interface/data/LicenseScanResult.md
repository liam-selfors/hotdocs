# `LicenseScanResult`

```json
{
  "component_id": "comp-foo",
  "gate_version": "license_scanner@3.1.0",
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

`matches` is non-empty only when `similarity_score` is above a reporting
floor (always populated on a flagged result; may be empty on a clean one).
Each match entry carries its reference's own `license_family` and
`risk_tier` — curated with the reference corpus, not computed here.
`blocked` is `similarity_score >= block_threshold` — confidence only.
`notified` is `(blocked) OR (any match's risk_tier == "high")`, **and**
`VAR-COMPLIANCE-WEBHOOK-URL` is configured — deliberately not a function of
`similarity_score` against a second threshold; the worked example above is
a *below-block-threshold, high-risk-tier* match that still notifies, which
is exactly the case a same-scale severity threshold couldn't express.
`notified` reflects whether a notification was **due**, from those
preconditions alone — never whether it was actually delivered.
`notification_delivery_error` is `{category, message}` or `null`
(`category` one of `network`/`auth`/`timeout`), populated only when
`notified` is `true` and the webhook call itself failed (`R-LICENSE-003`);
it never affects `blocked`.
