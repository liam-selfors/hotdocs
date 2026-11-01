# AC-SECRET-009

Covers: R-SECRET-009
Kind: generated-test

```gherkin
Given a repo_root whose gen/ file contains "AKIAABCDEFGHIJKLMNOP", a
  pattern database rule matching "AKIA[0-9A-Z]{16}", and a stand-in
  cache-manager that stores every put by key
When scan runs, the gen/ file is then rewritten with that string
  removed, and scan runs again
Then the first result is flagged and the second is not, put was
  called twice under two different keys, and the stored flagged result
  is still present after the second scan
```
