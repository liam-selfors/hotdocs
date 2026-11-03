# `Allowlist` and `AllowlistProposal`

`<repo_root>/.secret-allowlist.json` (`R-SECRET-012`):

```json
{
  "version": 1,
  "entries": [
    {
      "file": "verification/secret-scanner/generated-test/test_ac_secret_001.py",
      "type": "AWS Access Key",
      "hashed_secret": "sha1:abac545fc3bf803134bc8f78fb6160a5c6a87b26",
      "reason": "planted-fixture"
    }
  ]
}
```

It holds only a SHA-1 of a secret a person has reviewed and judged a
deliberate fixture or public constant. The `sha1:` prefix stops the
hex-entropy detector flagging the list itself.

`propose(repo_root)` returns (`R-SECRET-013`):

```json
{
  "allowlist": { "version": 1, "entries": [ "..." ] },
  "ineligible": [ { "file": "gen/foo/config.py", "line": 12, "rule_id": "AWS Access Key" } ]
}
```
