# AC-ENDPOINT-010

Covers: R-ENDPOINT-009
Kind: generated-test

```gherkin
Given detect_providers(env={"PATH": <dir without claude>, "OPENAI_API_KEY":
  "k", "GEMINI_API_KEY": " "}) with the Ollama probe's urlopen raising
Then it returns one entry per PROVIDERS name, each with provider,
  available, reason, suggested_model and api_key_env; only openai is
  available; and with a claude executable in PATH claude-cli is too

Given the Ollama probe's urlopen answering
When detect_providers runs
Then ollama is available, and the probe waited at most about a second

Given OPENAI_API_KEY set, and check_connection("openai", "m") with
  urlopen returning a normal reply, then raising HTTP 401
Then the results are {ok: true, error: null} and {ok: false, error:
  {category: "auth", ...}}; no call-log record is written; and an
  unknown provider raises ValueError
```
