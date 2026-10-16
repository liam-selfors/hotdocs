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
independently-designed mechanism.
