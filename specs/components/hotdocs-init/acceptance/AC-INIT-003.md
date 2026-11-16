# AC-INIT-003

Covers: R-INIT-003
Kind: generated-test

```gherkin
Given a tool root whose requirements.txt lists "pytest==9.2.0" and "no-such-pkg-xyz==1.0"
When init runs without --example
Then it returns 3 after creating the skeleton (a missing prerequisite never stops setup; no example is involved), output_fn received the lines "missing: no-such-pkg-xyz==1.0" and
  "  fix: pip install -r <tool_root>/requirements.txt", and no command was run

Given a requirements.txt of installed packages only, and provider claude-cli with env PATH holding no "claude"
When init runs
Then it returns 3 and output_fn received the two consecutive lines "missing: claude on PATH" and "  fix: install Claude Code and sign in" (among its other lines); with an executable "claude" file on that PATH it returns 0;
  and with provider ollama and no claude on PATH it returns 0
```
