---
id: VAR-GEMINI-API-KEY
title: Gemini API Key
status: draft
owners: [pipeline-team]
---

# VAR-GEMINI-API-KEY

- **required:** no
- **type:** secret-ref
- **sensitivity:** secret
- **description:** Credential `llm-endpoint` sends to the `gemini`
  provider, read from the process environment variable `GEMINI_API_KEY`,
  Google's own standard name (an exception to the `VAR_<NAME>` rule,
  like `VAR-ANTHROPIC-API-KEY`). `hotdocs.toml`'s `api_key_env` may name a
  different variable; this declaration covers the default. It is needed
  only when the `gemini` provider is used, and it travels in a request
  header, never the URL. No example or default, forbidden for any
  `sensitivity: secret` var.
