# R-VERIFY-019

**R-VERIFY-019** — For every `generated-test` criterion, this component
  MUST:

  1. treat a cached file as stale unless its first line is
     `# hotdocs-criterion: sha256:<hex>` with `<hex>` the SHA-256 of the
     criterion's `CriterionBundle` `criterion_text`, a newline, and its
     `requirement_text`, encoded UTF-8; a file with no such line is
     stale too. A stale file is ignored as if absent, so the test is
     authored again (R-VERIFY-009, `D320`).
  2. when a `test_author` call returns a `model_call_error` whose
     `category` is `network`, `timeout` or `rate_limit`, call it once
     more for that criterion. When the last call still returns a
     `model_call_error`, the test is never run: the criterion is `fail`
     with `failure_origin` `"test"` and `failure_detail.message`
     `test authoring failed: <category>: <message>` (`D319`).

  Every other failed criterion has `failure_origin` `"implementation"`.
