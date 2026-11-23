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

Given the first test source with 'static/app.js' replaced by
  'gen/app/static/app.js'
When probe(source, {}, "app") is called
Then ok is False, tests_reached is 0, and findings is exactly one
  test_bug finding whose message begins "test_filter: " and contains
  "HotdocsProbeUndeclaredAsset" and "is not a declared asset path"

Given the first test source unchanged
When probe(source, {}, "app", assets=["static/other.js"]) is called
Then ok is False and findings is exactly one test_bug finding whose
  message contains "'static/app.js' is not a declared asset path"

Given the first test source unchanged
When probe(source, {}, "app", assets=["static/app.js"]) is called
Then ok is True, findings is [] and tests_reached is 1
```
