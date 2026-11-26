# Testing agentic-generator

All are `kind: generated-test`, with a `llm-tool-endpoint` stand-in that
drives the tools from a script.

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
contains `bad`, else `(None, [])`, and
`check_asset_environment(component_id, repo_root=None)` returning
`("environment", ["fake needs fakeprog >= 2"])` when
`<repo_root>/NO_ENV` exists, else `(None, [])`. A bundle is any mapping with `component_id`,
`spec_bundle_hash` and `hint_code`.
