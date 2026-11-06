# `SecretScanResult`

```json
{
  "scope": "full",
  "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
  "flagged": false,
  "matches": [
    { "rule_id": "AWS Access Key", "risk_tier": "high", "file": "gen/foo/config.py", "line": 12 }
  ],
  "allowed": [
    { "rule_id": "AWS Access Key", "file": "verification/foo/test_x.py", "line": 3 }
  ],
  "unused_allowlist_entries": [
    { "file": "verification/foo/old.py", "type": "AWS Access Key" }
  ],
  "notified": false,
  "notification_delivery_error": null,
  "cache_hit": false
}
```

`scope` is `"full"` or `"precommit"`; a `precommit` result always has
`cache_hit: false` and MAY omit `gate_version` (`R-SECRET-008`).
`flagged` is `true` iff `matches` is non-empty. A match never carries
the secret or its hash (`R-SECRET-001`).

`allowed` lists every finding the allowlist suppressed and
`unused_allowlist_entries` every entry that matched nothing
(`R-SECRET-012`); neither affects `flagged`. An invalid allowlist adds
one match with `rule_id` `"allowlist-invalid"`.

Each match's `file` is relative to `repo_root` with `/` separators
(also in the precommit form); a path given to `scan_files` with no
`repo_root` is reported as given.

`notified` is `flagged` or any `high` match, **and**
`VAR-COMPLIANCE-WEBHOOK-URL` is configured (`R-LICENSE-003`): whether a
notification was **due**, never whether it was delivered. `notification_delivery_error` is
`{category, message}` or `null`, set only when `notified` is `true` and
the call failed (`R-SECRET-004`), and never affects `flagged`;
`category` is `auth` (HTTP 401/403), `timeout`, or `network` (anything
else).
