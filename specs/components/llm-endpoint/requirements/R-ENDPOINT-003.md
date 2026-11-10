# R-ENDPOINT-003

**R-ENDPOINT-003** — MUST implement exactly these providers, each as an
  adapter behind `R-ENDPOINT-002`'s resolve/dispatch split: `claude-cli`
  (the `claude` command), `anthropic` (Messages API), `openai` (Chat
  Completions), `openai-compatible` (the same wire format at a required
  `base_url`, covering OpenLLM, vLLM, LM Studio, LiteLLM, OpenRouter and
  similar servers), `gemini` (`generateContent`), and `ollama`. The HTTP
  providers use the Python standard library only, adding no dependency.
  A further provider is one more adapter and `PROVIDERS` entry, never a
  plugin or registry, and never a change to `complete()`
  (`R-ENDPOINT-001`) or any caller.

  **When `claude-cli` dispatches via the `claude` command's
  non-interactive mode (`D33`), it MUST pass `--tools ""` on every call**
  (`D35`), or the command keeps its tools. **It MUST also pass `--bare`
  when `ANTHROPIC_API_KEY` is set, or `--safe-mode` when it is not**
  (`D82`), since `--bare` refuses a subscription login. It MUST NOT check for a credential and refuse
  early; it dispatches and classifies what the command reports
  (`R-ENDPOINT-004`).

  **It MUST pass `--output-format stream-json --verbose`, and the reply
  is every text block of every `assistant` message, in order, joined with
  nothing between them** (`D225`): a long reply spans several messages,
  and plain output keeps only the last. A `result` line with `is_error`
  true is a failure; output that is not that stream is the reply as
  printed.
