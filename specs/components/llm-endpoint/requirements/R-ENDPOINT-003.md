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
  (`D35`): without it the command keeps its tool access
  (`Read`/`Bash`/etc.) despite instructions, a real `R-GEN-001`
  cold-mode purity violation caught live. **It MUST also pass `--bare`
  when `ANTHROPIC_API_KEY` is set, or `--safe-mode` when it is not**
  (`D82`): both suppress CLAUDE.md/hooks/plugin discovery, but `--bare`
  refuses any non-API-key credential, which would shut out a
  subscription login. It MUST NOT check for a credential and refuse
  early; it dispatches and classifies what the command reports
  (`R-ENDPOINT-004`).
