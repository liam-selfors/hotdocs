# R-GEN-006

**R-GEN-006** — `generate()` MUST NOT write to `cache-manager`.
  `commit_cache(result, repo_root)` MUST write a result that has `files`
  and no `model_call_error` or `refused` under the `R-GEN-005` key built
  from the result's `spec_bundle_hash`, `retry_feedback` and `model`, and
  MUST do nothing for any other result. Its caller calls it only after
  verification passes (`D305`).
