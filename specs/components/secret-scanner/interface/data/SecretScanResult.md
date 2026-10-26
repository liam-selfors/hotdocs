# `SecretScanResult`

```json
{
  "scope": "full",
  "gate_version": "secret_scanner@2.0.0",
  "flagged": false,
  "matches": [
    { "rule_id": "aws-access-key-id", "risk_tier": "high", "file": "gen/foo/config.py", "line": 12 }
  ],
  "notified": false,
  "notification_delivery_error": null,
  "cache_hit": false
}
```

`scope` is `"full"` or `"precommit"`. `gate_version` and `cache_hit` are
only meaningful for `scope: "full"` — a `precommit` result always has
`cache_hit: false` and MAY omit `gate_version` entirely, since R-SECRET-008
explicitly has no cache dependency. Each match entry carries its matched
rule's own `risk_tier`, curated with the pattern database, not computed
here. `notified` is `(flagged) OR (any match's risk_tier == "high")`, **and**
`VAR-COMPLIANCE-WEBHOOK-URL` is configured — the same orthogonal block/
severity split `license-scanner` uses (R-LICENSE-003), not a second,
independently-designed mechanism. `notified` reflects whether a
notification was **due**, from those preconditions alone — never
whether it was actually delivered. `notification_delivery_error` is
`{category, message}` or `null` (`category` one of `network`/`auth`/
`timeout`), populated only when `notified` is `true` and the webhook
call itself failed (`R-SECRET-004`); it never affects `flagged`.
