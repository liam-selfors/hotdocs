# AC-SECRET-010

Covers: R-SECRET-001
Kind: generated-test

```gherkin
Given gen/foo/e.py holding the lines
  token = "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH3jL5nP7r" and
  sha = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b"
When a full scan runs
Then matches holds exactly two entries, both risk_tier "low": rule_id
  "Base64 High Entropy String" on line 1 and "Hex High Entropy String"
  on line 2

Given the same token on an unquoted line: token = aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bD1fH3jL5nP7r
When a full scan runs
Then matches is empty (a known gap the library has, recorded in
  component.md)
```
