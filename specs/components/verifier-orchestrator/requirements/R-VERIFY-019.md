# R-VERIFY-019

**R-VERIFY-019** — Before running a `generated-test` criterion's test
  file, cached or newly authored, this component MUST:

  1. treat a cached file as stale when its first line is
     `# hotdocs-criterion: sha256:<hex>` and `<hex>` is not the SHA-256
     of the criterion's `CriterionBundle` `criterion_text`, a newline,
     and its `requirement_text`, encoded UTF-8; a stale file is ignored
     as if absent, so the test is authored again (R-VERIFY-009). A file
     with no such first line is never stale.
  2. pass the file's source, the bundle and the component's module name
     (its slug, hyphens replaced by underscores) to `test-probe`'s
     `probe`. When the report's `ok` is false and this file was not
     authored in this run, it MUST author the test again once, and probe
     the new file. A test that still fails its probe, or whose authoring
     returned a `model_call_error`, is never run: the criterion is `fail`
     with `failure_origin` `"test"` and `failure_detail.message`
     `test failed its probe: <error kinds, comma-separated>` or
     `test authoring failed: <category>`.

  Every other failed criterion has `failure_origin` `"implementation"`.
