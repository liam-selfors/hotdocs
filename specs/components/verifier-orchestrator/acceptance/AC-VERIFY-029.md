# AC-VERIFY-029

Covers: R-VERIFY-020
Kind: generated-test

```gherkin
Given comp-qux declaring assets: [fake:data/table.txt] with the fake
  kind planted, and one cached generated test asserting that
  asset_runner("data/table.txt")("b", []) == 2 and that
  asset_runner("data/other.txt") raises KeyError
When verify runs
Then that criterion is pass

Given the same, and a test-probe stand-in that records each call's
  keyword arguments and returns ok True
When verify runs
Then every recorded call has assets ["data/table.txt"]
```
