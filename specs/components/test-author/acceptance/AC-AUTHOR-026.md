# AC-AUTHOR-026

Covers: R-AUTHOR-026
Kind: generated-test

```gherkin
Given a bundle whose component_id is "capabilities/P-SLUGS" and whose
  module_names is ["slugify", "url_tools"]
When author_test builds its prompt
Then the prompt contains "import slugify" and "import url_tools", and
  never contains "import capabilities"

Given a bundle whose component_id is "comp-semver" and whose
  module_names is []
When author_test builds its prompt
Then the prompt contains "import semver"
```
