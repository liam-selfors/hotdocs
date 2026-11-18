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
     more for that criterion (`D319`).
  3. pass the file's source, the bundle and the component's module name
     (its slug, hyphens replaced by underscores) to `test-probe`'s
     `probe`. When the report's `ok` is false and this file was not
     authored in this run, author the test again once and probe the new
     file (`D307`).

  A test that still fails its probe, or whose last authoring call
  returned a `model_call_error`, is never run: the criterion is `fail`
  with `failure_origin` `"test"` and `failure_detail.message`
  `test failed its probe: <error kinds, comma-separated>` or
  `test authoring failed: <category>: <message>`.

  Every other failed criterion has `failure_origin` `"implementation"`.
