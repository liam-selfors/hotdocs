# AC-LINT-032

Covers: R-LINT-032
Kind: generated-test

```gherkin
Given a project holding .hotdocs-tool.json with components "foo" and "cache-manager"
When the linter runs on it
Then "cache-manager" gets an R-LINT-032 fail finding and "foo" none

Given the same project without .hotdocs-tool.json, or the tool's own repository
When the linter runs on it
Then there is no R-LINT-032 finding
```
