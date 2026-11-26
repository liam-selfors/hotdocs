# AC-RUNENV-004

Covers: R-RUNENV-004
Kind: generated-test

```gherkin
Given the fake kind and the fake driver declared, and a test file with
  two test functions: one taking asset_runner and fake_session and
  asserting asset_runner("data/table.txt")("b", []) == 2 and
  fake_session.value == "open"; one taking asset_runner and asserting
  that asset_runner("other.txt") raises KeyError whose args[0] is
  "asset_runner: 'other.txt' is not a declared asset (declared:
  data/table.txt)"
When prepare runs and pytest runs that file as testing.md describes
Then pytest exits 0, closed.log holds exactly one line "closed", and
  after close() plugin_dir no longer exists
```
