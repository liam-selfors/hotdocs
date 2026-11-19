# Library

One module file, `agentic_generator.py`, never a package.

```
generate_agentic(bundle: SpecBundle, model: str, retry_feedback: list[str] | None = None,
                 *, repo_root: Path = None, allow_unisolated_exec: bool = False,
                 max_turns: int = 40, max_tool_calls: int = 120,
                 wall_seconds: float = 1800.0, claude_command: str = "claude") -> GenerationResult
AGENT_PROMPT_VERSION = "agent-v1"
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
`check_write_allowed`, `render_prompt_sections`, `write_files` and
`check_assets` from the first, `run_tool_loop` from the second.

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

## Test fixtures

A **loop stand-in** is `<repo_root>/gen/llm-tool-endpoint/llm_tool_endpoint.py`
defining `run_tool_loop(system, prompt, model, tools, execute, *,
max_turns=40, max_tool_calls=120, wall_seconds=1800.0, repo_root=None,
claude_command="claude")` that records its arguments to a file, calls
`execute(name, arguments)` for each step of a script the test wrote to
a JSON file, records each `(name, arguments, text, is_error)` it gets
back, and returns an object with `text`, `transcript`, `turns`,
`tool_calls`, `stop` and `model_call_error`.

A **generator stand-in** is `<repo_root>/gen/generator/generator.py`
defining `GenerationResult` as a dataclass with `generator`'s fields in
order, every one defaulted (`component_id=""`, `spec_bundle_hash=""`,
`model=""`, `prompt_version=""`, `cache_hit=False`, `files={}`,
`model_call_error=None`, `refused=None`, `retry_feedback=None`,
`mode="single"`, `transcript_sha256=None`, `turns=1`, `tool_calls=0`,
`isolation=None`), `check_write_allowed(bundle, repo_root=None)`
returning `None`, `render_prompt_sections(bundle, retry_feedback=None)`
returning `[("Spec", "SPEC TEXT"), ("Component interface", "IFACE TEXT")]`,
`write_files(component_id, files, repo_root=None)` recording its
arguments to a file, and `check_assets(component_id, files,
repo_root=None)` recording its arguments to a file and returning
`("malformed_layout", ["static/app.txt: bad"])` when some file's content
contains `bad`, else `(None, [])`. A bundle is any mapping with `component_id`,
`spec_bundle_hash` and `hint_code`.

Implements: `specs/architecture/agent-sandbox.md`
