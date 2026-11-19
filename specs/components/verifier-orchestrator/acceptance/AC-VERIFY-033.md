# AC-VERIFY-033

Covers: R-VERIFY-020
Kind: generated-test

```gherkin
Given comp-qux declaring no assets with verifier-fixtures.md's failing
  python adapter planted, and one cached passing generated test
When verify runs
Then the criterion is "fail" with failure_origin "environment" and
  failure_detail.message "python environment: broken"

Given the wrapped python adapter is planted instead
When verify runs
Then the criterion is pass and wrapper.log holds at least two lines
  "called"
```
