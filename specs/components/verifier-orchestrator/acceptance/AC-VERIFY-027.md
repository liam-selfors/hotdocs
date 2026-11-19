# AC-VERIFY-027

Covers: R-VERIFY-019
Kind: generated-test

```gherkin
Given comp-qux whose qux() returns 2 * 2 and two generated-test
  criteria whose current cached tests assert qux.qux() == 4, the second
  also asserting (Path.cwd() / "specs").is_dir()
When verify runs
Then the first criterion is pass; the second is fail, failure_origin
  "test", message "test fails in the mutation sandbox", and its file is
  deleted; mutation_error is None and mutation_score is not None
```
