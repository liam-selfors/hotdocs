# AC-PROVCHECK-006

Covers: R-PROVCHECK-004
Kind: compiled

```gherkin
Given gen/comp-foo/.provenance.json exists
When check_provenance is called for comp-foo, on either a hit or a miss
Then the file's content and mtime are unchanged and no other file is
  written
```
