# R-VERIFY-019

**R-VERIFY-019** — For every `generated-test` criterion, this component
  MUST:

  1. treat a cached file as stale unless its first line is the header
     `specs/architecture/test-reuse.md` defines for the criterion's
     `CriterionBundle`, and author a stale one again (`D320`, `D341`).
  2. when `test_author` returns a `model_call_error` whose `category` is
     `network`, `timeout` or `rate_limit`, call it once more (`D319`).
  3. pass the file's source, the bundle, the module name (the slug,
     hyphens as underscores) and `interpreter=` the `python` report's
     `interpreter` (`D344`) to `test-probe`'s `probe`; when `ok` is
     false and the file was not authored in this run, author it again
     once and probe the new file (`D307`).

  A test that still fails its probe, or whose last authoring call
  returned a `model_call_error`, is never run: the criterion is `fail`
  with `failure_origin` `"test"` and `failure_detail.message`
  `test failed its probe: <error kinds, comma-separated>` or
  `test authoring failed: <category>: <message>`. A test failing alone
  in the mutation sandbox is handled as `test-reuse.md`'s "Mutation
  runs" says. Every other failed criterion has `failure_origin`
  `"implementation"`, except `R-VERIFY-020`'s `"environment"`.
