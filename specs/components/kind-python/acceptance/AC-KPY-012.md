# AC-KPY-012

Covers: R-KPY-009
Kind: generated-test

```gherkin
Given the module kind_python
When guidance() is called twice
Then each result == {"generator": "", "test_author": ""}, and adding a
  key to one result does not change the other
```
