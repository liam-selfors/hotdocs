# AC-PROBE-007

Covers: R-PROBE-003
Kind: generated-test

```gherkin
Given the test source
  "import slugify\nimport url_tools\n\ndef test_a():\n    assert url_tools.join(slugify.slugify('A')) == 'a'\n"
When probe(source, {}, ["slugify", "url_tools"]) is called
Then ok is True, no finding has kind "unknown_import", tests_run is 1
  and tests_reached is 1

Given the same source
When probe(source, {}, "slugify") is called
Then ok is False and the findings hold exactly one unknown_import
  finding, with line 2 and message "cannot import 'url_tools'"
```
