# R-AGENT-005

**R-AGENT-005** — When `finish` was called, the candidate MUST be every
  regular file under `work/`, keyed by its path relative to `work/`,
  read as UTF-8; a file that does not decode gives `model_call_error`
  category `undecodable_file`. With neither `<module>.py` nor
  `<module>/__init__.py` among them, the category is `missing_module`.
  Otherwise `check_assets(bundle["component_id"], <candidate>,
  repo_root=repo_root)` is called once, in either mode; a category it
  returns is the category, its messages joined by `"\n"` the message,
  and nothing is written (`D343`).
  Otherwise `files` is that candidate, in cold mode
  (`bundle["hint_code"]` is `None`) also written by one call
  `write_files(bundle["component_id"], files, repo_root=repo_root)`; in
  hint mode nothing is written and `hint_code` is never returned as
  `files`. Every result has `mode` `"agentic"`, `cache_hit` false,
  `prompt_version` `AGENT_PROMPT_VERSION`, `retry_feedback` and
  `spec_bundle_hash` echoed, the loop's `turns` and `tool_calls`, the
  `isolation`, and `transcript_sha256` `"sha256:"` plus the SHA-256 hex
  digest of `json.dumps(transcript, sort_keys=True, default=str)`
  encoded UTF-8.
