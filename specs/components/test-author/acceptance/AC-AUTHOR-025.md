# AC-AUTHOR-025

Covers: R-AUTHOR-025
Kind: generated-test

```gherkin
Given a bundle whose component_id is "comp-foo-bar"
When author_test builds its prompt
Then the prompt states that the component under test is imported with
  "import foo_bar", and never instructs "import comp_foo_bar"

Given a bundle whose component_id is "comp-semver"
When author_test builds its prompt
Then the prompt states "import semver"
```
