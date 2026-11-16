# AC-SECRET-001

Covers: R-SECRET-001
Kind: generated-test

Each scenario builds a temporary `repo_root`, with a stand-in
`cache-manager` and no allowlist file, and calls `scan(repo_root)`.

```gherkin
Given gen/foo/config.py holding the line K = "AKIAABCDEFGHIJKLMNOP"
When a full scan runs
Then matches holds exactly one entry: rule_id "AWS Access Key",
  risk_tier "high", file "gen/foo/config.py", line 1, and flagged is true

Given the same key in README.md, notes/n.md, pipeline/p.py, tools/t.py,
  and verification/secret-scanner/generated-test/test_x.py
When a full scan runs
Then each of those five files has a match
```

```gherkin
Given the same key inside gen/foo/__pycache__/x.txt,
  .git/config, .venv/lib/x.py, .hotdocs/x.json, .pytest_cache/x.txt,
  node_modules/x.js, and a file gen/foo/blob.bin holding bytes that are
  not valid UTF-8 and include that key
When a full scan runs
Then flagged is false and matches is empty
```

```gherkin
Given gen/foo/ok.py holding the lines gate_version=GATE_VERSION,
  {"secret_scanner": "secret_scanner@0.0.0"}, and
  see verification/spec-linter/BOOTSTRAP.md --retry-feedback=R-TRACK-009
When a full scan runs
Then flagged is false and matches is empty
```
