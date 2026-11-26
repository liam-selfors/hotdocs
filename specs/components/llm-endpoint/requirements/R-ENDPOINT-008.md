# R-ENDPOINT-008

**R-ENDPOINT-008** — Each HTTP adapter MUST speak its provider's
  documented wire format (`D180`), with a descriptive `User-Agent`. The
  caller's `max_tokens` and `temperature` params are understood;
  `ollama` also takes `num_ctx`; other params are ignored.

  | provider | request | auth | answer |
  | --- | --- | --- | --- |
  | `anthropic` | `POST {base}/v1/messages`, `anthropic-version: 2023-06-01`, `max_tokens` always sent (default 32000) | `x-api-key` | the `text` blocks of `content`, joined (thinking blocks may precede them) |
  | `openai` | `POST {base}/chat/completions`, `max_completion_tokens` | `Authorization: Bearer` | `choices[0].message.content` |
  | `openai-compatible` | as `openai`, `max_tokens` | Bearer, only if a key is configured | as `openai` |
  | `gemini` | `POST {base}/v1beta/models/{model}:generateContent`, `generationConfig.maxOutputTokens` | `x-goog-api-key` header, never the URL | the non-`thought` text parts of `candidates[0].content` |
  | `ollama` | `POST {base}/api/chat`, `stream` false, `options.num_predict` | none (Bearer if a key is configured) | `message.content` |

  A `gemini` model written `models/<name>` is
  sent as `<name>`. An `openai-compatible` `base_url` includes
  its version prefix (e.g. `http://localhost:8000/v1`).
