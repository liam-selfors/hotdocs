---
id: VAR-OPENAI-API-KEY
title: OpenAI API Key
status: draft
owners: [pipeline-team]
---

# VAR-OPENAI-API-KEY

- **required:** no
- **type:** secret-ref
- **sensitivity:** secret
- **description:** Credential `llm-endpoint` sends to the `openai`
  provider, read from the process environment variable `OPENAI_API_KEY`,
  OpenAI's own standard name (an exception to the `VAR_<NAME>` rule,
  like `VAR-ANTHROPIC-API-KEY`). `hotdocs.toml`'s `api_key_env` may name a
  different variable; this declaration covers the default. It is needed
  only when the `openai` provider is used. No example or default,
  forbidden for any `sensitivity: secret` var.
