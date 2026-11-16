# AC-PROBE-005

Covers: R-PROBE-005
Kind: generated-test

```gherkin
Given a test source that imports pytest and "from slugify import slugify"
  and defines five tests: test_reach asserting slugify("A") == "a";
  test_guarded calling slugify("") inside pytest.raises(Exception);
  test_missing taking a fixture argument named no_such_fixture;
  test_constant asserting 1 == 1; and test_wrong asserting
  int("x") == 1
When probe(source, {}, "slugify") is called
Then tests_run is 5 and tests_reached is 2; the findings are one test_bug
  finding whose message starts "test_missing: " and one vacuous finding,
  severity "warn", whose message is
  "test_constant passed without reaching the code under test"; and ok
  is False

Given a test source whose only test calls time.sleep(30)
When probe(source, {}, "slugify", timeout=2) is called
Then the findings are exactly one probe_timeout finding and ok is False
```
