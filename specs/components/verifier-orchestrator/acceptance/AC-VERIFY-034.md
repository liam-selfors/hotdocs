# AC-VERIFY-034

Covers: R-VERIFY-004
Kind: generated-test

The fixture component `comp-foo`: `gen/foo/foo.py` holds exactly
`def run(a, b):\n    return a\n`, and
`specs/components/foo/interface/library.md` holds, in order, a fenced
block opened by three backticks alone holding the one line `run(a, b)`,
then a fenced block opened by three backticks and `python` holding the
lines `class Helper:`, `    def __init__(self, name):`, `        pass`
and `build(x)`.

```gherkin
Given that fixture
When verify runs on comp-foo
Then interface_drift is false
And after the bare block's line is changed to run(a, b, c),
  interface_drift is true and the overall verdict is fail
```
