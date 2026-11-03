# AC-SECRET-009

Covers: R-SECRET-009
Kind: generated-test

```gherkin
Given a repo_root whose gen/foo/c.py holds K = "AKIAABCDEFGHIJKLMNOP"
  and a stand-in cache-manager that stores every put by key
When scan runs, gen/foo/c.py is then rewritten with that key removed,
  and scan runs again
Then the first result is flagged and the second is not, put was called
  twice under two different keys, and the stored flagged result is still
  present after the second scan
```
