# R-AUTHOR-008

**R-AUTHOR-008** — `VAR-ANTHROPIC-API-KEY` MUST never appear in output,
  logs, or provenance — only the model identifier actually used is
  recorded. Since `D18`, this component no longer holds that credential
  at all (`llm-endpoint`/`R-ENDPOINT-005` does), so this is now a
  structural guarantee, not just a checked one — stated here regardless,
  as the component-local half of that guarantee's coverage.
