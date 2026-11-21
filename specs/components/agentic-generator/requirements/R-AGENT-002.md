# R-AGENT-002

**R-AGENT-002** — `generate_agentic` MUST build the sandbox exactly as
  `specs/architecture/agent-sandbox.md`'s Layout says, from
  `render_prompt_sections(bundle, retry_feedback)`, and call
  `run_tool_loop` once with the seven tools, `model`, the budgets and
  `claude_command` it was given, and `repo_root`. The system text states
  the sandbox layout, naming the directories `bundle/`, `work/`,
  `scratch/` and `tmp/`; that `work/` is the only output and must hold
  `<module>.py` or `<module>/__init__.py`, written with the component's
  actual module name substituted, plus each asset path the component
  declares (`specs/architecture/asset-kinds.md`), and no other non-`.py`
  file; that `scratch/` is discarded; that the
  model has no other access; and that it calls the tool `finish` when
  done. The prompt names every `bundle/` file by its path relative to
  `<root>` (`bundle/<NN>-<slug>.md`), in position order, and asks the
  model to read them all before writing.
