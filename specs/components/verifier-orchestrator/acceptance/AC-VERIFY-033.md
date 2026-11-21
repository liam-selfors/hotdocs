# AC-VERIFY-033

Covers: R-VERIFY-020
Kind: generated-test

```gherkin
Given comp-qux declaring no assets with verifier-fixtures.md's failing
  python adapter planted, one cached passing generated test and one
  passing compiled criterion
When verify runs
Then both criteria are "fail" with failure_origin "environment" and
  failure_detail.message "python environment: broken"

Given the wrapped python adapter instead, its wrapper exec'ing
  sys.executable unresolved
When verify runs
Then both criteria pass and wrapper.log holds at least two lines
  "called"
```
