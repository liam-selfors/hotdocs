# Library

One module file, `agentic_generator.py`, never a package.

```
generate_agentic(bundle: SpecBundle, model: str, retry_feedback: list[str] | None = None,
                 *, repo_root: Path = None, allow_unisolated_exec: bool = False,
                 max_turns: int = 40, max_tool_calls: int = 120,
                 wall_seconds: float = 1800.0, claude_command: str = "claude") -> GenerationResult
AGENT_PROMPT_VERSION = "agent-v2"
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
BWRAP = "bwrap"
```

The OS sandbox is chosen when a command runs, from the module-level
`SANDBOX_EXEC` (used on macOS when that file exists) and `BWRAP` (used on
Linux when `shutil.which(BWRAP)` finds it); a test makes both
unavailable by setting them to a path that does not exist.

`GenerationResult` is `generator`'s, built with `generator`'s own
dataclass. `generator` and `llm-tool-endpoint` are loaded from
`<repo_root>/gen/<slug>/<module>.py`, else from the tool root's copy:
`check_write_allowed`, `render_prompt_sections`, `write_files`,
`check_assets` and `check_asset_environment` from the first, `run_tool_loop` from the second.

`generate_agentic` reads a bundle's fields only by subscript
(`bundle["component_id"]`, `bundle["spec_bundle_hash"]`,
`bundle["hint_code"]`), so a plain dict works as a bundle. Every
`model_call_error` it returns is a dict `{"category": <str>,
"message": <str>}`, the shape `ToolLoopResult` uses. An exception raised
by `run_tool_loop`, or by a helper loaded from `generator`, propagates
out of `generate_agentic` unchanged, after the sandbox is removed
(`R-AGENT-007`); it is never turned into a `GenerationResult`.

`<module>` is the component's slug with hyphens replaced by underscores.
The tools, path rules, limits, environment and OS sandbox are
`specs/architecture/agent-sandbox.md`'s; each tool is given to
`run_tool_loop` as `{"name", "description", "input_schema"}`, every
argument a required string property.

Implements: `specs/architecture/agent-sandbox.md`, `specs/architecture/asset-kinds.md`
