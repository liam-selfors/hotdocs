# AC-PROBE-009

Covers: R-PROBE-008
Kind: generated-test

```gherkin
Given the planted wrapper interpreter, whose Python alone can import
  wraponly_pkg, and the test source
  "import wraponly_pkg\nimport slugify\n\n\ndef test_w():\n    assert slugify.slugify('x') == 'x'\n"
When probe(source, {}, "slugify", interpreter=<the wrapper's path>) is called
Then ok is True, findings is [], tests_run is 1 and tests_reached is 1

Given the same test source
When probe(source, {}, "slugify") is called
Then ok is False and findings is exactly one unknown_import finding,
  line 1, message "cannot import 'wraponly_pkg'"
```
