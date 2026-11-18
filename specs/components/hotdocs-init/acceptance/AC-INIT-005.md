# AC-INIT-005

Covers: R-INIT-005
Kind: generated-test

```gherkin
Given fake check_connection returning {ok true}
When init runs with --provider openai --model m --api-key-env MY_KEY
Then it prints "connection ok", saves via save_config(<dir>/hotdocs.toml, "openai", "m", api_key_env="MY_KEY")
  with no base_url and no timeout_seconds keyword, and asks nothing

Given check_connection returns {ok false, error {category "auth", message "bad"}}
When init runs interactively and the answer to "Save anyway? [y/N]" is "n", then in another run in a fresh directory and tool root "y"
Then it printed "connection failed: auth: bad", and saved only in the second run

Given check_connection raises ValueError("no base_url")
When init runs
Then it printed "connection failed: invalid: no base_url"

Given save_config raises ValueError("nope")
When init runs
Then stderr holds "could not save: nope", init carries on, and the exit code is not changed by it

Given --no-test
When init runs
Then check_connection was never called

Given fake check_connection returning {ok true}
When init runs with --provider claude-cli --model m --auth login --yes
Then check_connection received auth "login", and it saves via
  save_config(<dir>/hotdocs.toml, "claude-cli", "m", auth="login")
```
