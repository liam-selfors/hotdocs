# AC-PROBE-003

Covers: R-PROBE-003
Kind: generated-test

```gherkin
Given the test source
  "import json\nimport your_module_here\nfrom slugify import slugify\ntry:\n    import nosuchpkg_optional\nexcept ImportError:\n    nosuchpkg_optional = None\n\ndef test_a():\n    assert slugify('A') == 'a'\n"
When probe(source, {}, "slugify") is called
Then ok is False and the findings hold exactly one unknown_import finding,
  with line 2 and message "cannot import 'your_module_here'"

Given the same source without its second line
When probe(source, {}, "slugify") is called
Then no finding has kind "unknown_import"

Given a test source holding, each on its own line, "from . import helpers",
  "from os import path", "import xml.etree.ElementTree", and a try block
  "import yaml_nonexistent_q" whose except clause is "except
  (OSError, ImportError):", plus one test asserting path.sep
When probe(source, {}, "slugify") is called
Then no finding has kind "unknown_import"
```
