# R-ENDPOINT-003

**R-ENDPOINT-003** — MUST implement exactly these providers, each as an
  adapter behind `R-ENDPOINT-002`'s resolve/dispatch split: `claude-cli`
  (the `claude` command), `anthropic` (Messages API), `openai` (Chat
  Completions), `openai-compatible` (the same wire format at a required
  `base_url`), `gemini` (`generateContent`), and `ollama`. The HTTP
  providers use the Python standard library only, adding no dependency.
  A further provider is one more adapter and `PROVIDERS` entry, never a
  plugin or registry, and never a change to `complete()`
  (`R-ENDPOINT-001`) or any caller.

  **`claude-cli` MUST run the `claude` command's non-interactive mode
  (`D33`) exactly as `specs/architecture/claude-cli-adapter.md` gives**:
  its arguments, its environment under `hotdocs.toml`'s `auth` entry,
  how its output becomes the reply, and how a failure is classified and
  worded (`D35`, `D82`, `D225`, `D322`).
