# AC-PROBE-006

Covers: R-PROBE-006
Kind: generated-test

```gherkin
Given a test source whose one test asserts slugify("A") == "a"
When probe(source, {}, "slugify") is called
Then ok is True, findings is [], tests_run is 1, tests_reached is 1,
  and no directory whose name tempfile.gettempdir() lists was added by
  the call

Given a test source with an undefined name on line 4 and an unknown
  import on line 1
When probe(source, {}, "slugify") is called
Then the unknown_import finding comes after the undefined_name finding,
  and report.to_dict() is a dict whose "findings" entries each have the
  keys kind, severity, line and message
```
