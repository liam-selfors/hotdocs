# AC-PROBE-006

Covers: R-PROBE-006
Kind: generated-test

```gherkin
Given a test source whose one test asserts slugify("A") == "a"
When probe(source, {}, "slugify") is called
Then ok is True, findings is [], tests_run is 1, tests_reached is 1,
  and no directory whose name tempfile.gettempdir() lists was added by
  the call

Given the test source
  "import zz_no_such_module_q\n\ndef test_x():\n    assert undefined_q == 1\n",
  an unknown import on line 1 and an undefined name on line 4
When probe(source, {}, "slugify") is called
Then the unknown_import finding comes after the undefined_name finding,
  and report.to_dict() is a dict whose "findings" entries each have the
  keys kind, severity, line and message

Given a test source with two undefined names on the same line 5, "zeta_q"
  then "alpha_q"
When probe(source, {}, "slugify") is called
Then the two undefined_name findings are ordered by message: "undefined
  name 'alpha_q'" before "undefined name 'zeta_q'"
```
