# R-ENDPOINT-009

**R-ENDPOINT-009** — MUST expose the setup helpers `hotdocs init` builds
  on, all in `interface/library.md`: `PROVIDERS` (per provider
  `default_base_url`, `default_api_key_env`, `needs_base_url`,
  `suggested_model`; the suggestion is a hint, never applied by
  `complete()`); `save_config`, which validates exactly as
  `load_config` does, refuses an unknown provider or anything that looks
  like a secret, writes nothing then, keeps any other content of an
  existing file, and writes no secret; `detect_providers`, one entry per
  provider saying whether it looks usable now (`claude` on `PATH`, a
  non-blank key variable, an Ollama server answering within about a
  second), reading only the `env` it is given; and `check_connection`,
  one tiny real completion reporting `{ok, error}` with the same
  `error` shape as `model_call_error`, never logged as a pipeline call,
  never echoing a key.
