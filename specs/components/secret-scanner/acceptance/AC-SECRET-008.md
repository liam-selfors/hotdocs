# AC-SECRET-008

Covers: R-SECRET-008
Kind: generated-test

```gherkin
Given verification/foo/t.py holding K = "AKIAABCDEFGHIJKLMNOP", allowlisted
  and sealed as in AC-SECRET-014's first scenario, and src/c.py
  holding C = "AKIAZZZZYYYYXXXXWWWW", and a recording
  cache-manager stand-in
When scan_files([<both files>], repo_root=<repo_root>) runs
Then scope is "precommit", matches holds only file
  "src/c.py", allowed holds file "verification/foo/t.py", and the
  stand-in recorded no call
```
