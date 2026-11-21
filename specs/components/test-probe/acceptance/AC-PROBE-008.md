# AC-PROBE-008

Covers: R-PROBE-007
Kind: generated-test

```gherkin
Given the test source
  "def test_filter(asset_runner):\n    run = asset_runner('static/app.js')\n    assert run('filterNodes', [[], 'gen']) == []\n"
When probe(source, {}, "app") is called
Then ok is True, findings is [], tests_run is 1 and tests_reached is 1

Given the test source
  "def test_lookup(asset_runner):\n    run = asset_runner('static/other.js')\n    assert callable(run)\n"
When probe(source, {}, "app") is called
Then ok is True, tests_run is 1, tests_reached is 0, and findings is
  exactly one vacuous finding, severity "warn", message
  "test_lookup passed without reaching the code under test"
```
