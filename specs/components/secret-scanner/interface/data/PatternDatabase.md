# `PatternDatabase`

The JSON file `VAR-SECRET-PATTERNS-PATH` names (a relative path
resolves against `repo_root` in `scan` and `gate_version`, and against
the current directory in `scan_files`):

```json
{
  "version": "2.0.0",
  "rules": [
    {"rule_id": "aws-access-key-id", "risk_tier": "high",
     "pattern": "AKIA[0-9A-Z]{16}"}
  ]
}
```

`pattern` is a Python regular expression matched against each line.
A rule missing `rule_id`, `risk_tier`, or `pattern`, or whose
`pattern` does not compile, is skipped. A missing, unreadable, or
malformed file means no rules and `version` `"0.0.0"`
(`R-SECRET-001`).

**`gate_version`** is `secret_scanner@<version>` (`R-SECRET-006`).
