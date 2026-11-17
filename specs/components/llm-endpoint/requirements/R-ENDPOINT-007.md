# R-ENDPOINT-007

**R-ENDPOINT-007** — Provider choice MAY be configured in a committed
  `hotdocs.toml`, which MUST never hold a secret. Its one table is:

  ```toml
  [llm]
  provider = "openai"            # required: a name from R-ENDPOINT-003
  model = "gpt-6-astra"          # required: the model setup chose
  base_url = ""                  # optional http(s) URL; required for openai-compatible
  api_key_env = "OPENAI_API_KEY" # optional: the NAME of the variable
  timeout_seconds = 600          # optional; at least 300
  auth = "login"                 # optional, claude-cli only: "login" or "key"
  ```

  Discovery: the file `VAR-HOTDOCS-CONFIG` names (a missing file is an
  error), else `hotdocs.toml` in the current directory, else none.
  `load_config` returns the validated table, `None` when there is no file or
  it has no `[llm]` table,
  and raises `ValueError` naming the problem otherwise; for a file that
  does not parse, the message contains `not valid TOML`. An empty
  `base_url` or `api_key_env` reads as unset. An unknown entry
  is invalid; an entry whose name suggests a secret (`api_key`, `token`,
  `password`...) is rejected with a message saying so. `api_key_env`
  MUST be a variable name: a value that fits the name pattern but equals
  some environment variable's value is a pasted key and is rejected.
  `claude-cli` takes no `base_url` or `api_key_env`, and only
  `claude-cli` takes `auth`; any other `auth` value is invalid.
