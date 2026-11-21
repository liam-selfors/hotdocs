# AC-VERIFY-030

Covers: R-VERIFY-020
Kind: generated-test

```gherkin
Given comp-qux declaring assets: [fake:data/table.txt], whose fake
  adapter's provision reports ok False with reason
  "fake needs fakeprog >= 2", one generated-test criterion with no
  cached test, and a test_author stand-in recording its calls
When verify runs with that test_author
Then test_author was never called, the criterion is "fail" with
  failure_origin "environment" and failure_detail.message
  "fake needs fakeprog >= 2", mutation_score is None, overall is "fail"

Given comp-qux instead declares assets: [nokind:data/table.txt]
When verify runs
Then the criterion's failure_detail.message is
  "unknown asset kind: nokind" and its failure_origin "environment"
```
