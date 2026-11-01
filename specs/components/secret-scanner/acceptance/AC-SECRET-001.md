# AC-SECRET-001

Covers: R-SECRET-001
Kind: generated-test

```gherkin
Given a file under gen/ containing a string matching a known API-key shape
When a full secret-scan runs
Then that file is reported in matches
```

```gherkin
Given gen/foo/__pycache__/x.txt containing "AKIAABCDEFGHIJKLMNOP", and
  gen/foo/blob.bin holding bytes that are not valid UTF-8 and include
  that same string, with a pattern database rule matching
  "AKIA[0-9A-Z]{16}"
When a full scan runs
Then flagged is false and matches is empty
```
