# R-SUPPLY-003

**R-SUPPLY-003** — Every test `supply` would return MUST first pass
  `test-probe`'s `probe(source, bundle, module_name, interpreter=...,
  assets=..., drivers=...)`, `module_name` the slug with `-` as `_`.
  When a committed test fails its probe, `supply` authors once
  (`R-SUPPLY-002`) and probes the new file (`D307`); when an authored
  test fails, it is not authored again. A test still failing gives
  `failure_origin` `"test"` and `failure_message`
  `test failed its probe: <kinds>`, the distinct `kind` values of that
  report's findings with `severity` `"error"`, in order of first
  appearance, joined by `", "`.
