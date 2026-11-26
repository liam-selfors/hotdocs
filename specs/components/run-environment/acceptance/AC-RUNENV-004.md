# AC-RUNENV-004

Covers: R-RUNENV-004
Kind: generated-test

```gherkin
Given the fake kind and the fake driver declared, and a test file
  asserting asset_runner("data/table.txt")("b", []) == 2 and
  fake_session.value == "open", and a second asserting that
  asset_runner("other.txt") raises KeyError with the message
  "asset_runner: 'other.txt' is not a declared asset (declared:
  data/table.txt)"
When prepare runs and pytest runs both files as testing.md describes
Then pytest exits 0, closed.log holds one line "closed", and after
  close() plugin_dir no longer exists
```
