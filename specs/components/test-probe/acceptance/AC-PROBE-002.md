# AC-PROBE-002

Covers: R-PROBE-002
Kind: generated-test

```gherkin
Given the test source
  "import os\nfrom slugify import slugify\n\ndef test_a():\n    assert slugify(tmp_dir) == 'x'\n"
  (os imported and unused, tmp_dir never defined)
When probe(source, {}, "slugify") is called
Then ok is False and the only finding is of kind "undefined_name",
  severity "error", line 5 and message "undefined name 'tmp_dir'"
```
