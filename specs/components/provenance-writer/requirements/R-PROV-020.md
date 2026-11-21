# R-PROV-020

**R-PROV-020** — `write_provenance` MUST write, in the manifest:
  `generation` as `{"mode", "generator_version", "transcript_sha256",
  "turns", "tool_calls", "isolation"}`, each copied from
  `generation_result` except `generator_version`, which is
  `gate_versions["generator"]` (`null` when absent), and `mode` `"single"`
  when the result's `mode` is absent or `null`; `attempts` as `inputs.attempts`; and
  `attempt_history` as `inputs.attempt_history` (`[]` when absent), each
  entry keeping only `number`, `outcome`, `retry_feedback`,
  `error_category`, `failed_requirements` and `transcript_sha256`. No
  other field of an attempt or of `generation_result`, and no transcript
  (such as `generation_result.transcript`), is ever written to either
  manifest file.
