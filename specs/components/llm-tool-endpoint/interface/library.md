# Library

One module file, `llm_tool_endpoint.py`, never a package.

```
run_tool_loop(system: str, prompt: str, model: str, tools: list[dict],
              execute, *, max_turns: int = 40, max_tool_calls: int = 120,
              wall_seconds: float = 1800.0, repo_root: Path = None,
              claude_command: str = "claude") -> ToolLoopResult
serve_mcp(socket_path: str, tools_path: str) -> int
class ToolUseUnsupported(Exception)
```

`tools` holds `{"name", "description", "input_schema"}` dicts.
`execute(name: str, arguments: dict) -> tuple[str, bool]` runs one call
and returns its result text and whether it is an error; it is always
called positionally, `arguments` being the call's argument object
unchanged. `model` is a
model string (`llm-endpoint`'s `R-ENDPOINT-002`), resolved with
`llm-endpoint`'s `resolve_provider(model, load_config())`, `load_config`
called with no argument; the API key is read from the environment
variable the resolved `api_key_env` names. `llm-endpoint` is loaded from
`<repo_root>/gen/llm-endpoint/llm_endpoint.py` when `repo_root` is given
and that file exists, else from the same path under the tool root, the
parent of the nearest directory named `gen` above this module's own file
(`D199`). `repo_root` affects nothing else. `ModelResolutionError` from
it propagates.

Every HTTP request is `urllib.request.urlopen(request, timeout=<seconds>)`,
looked up on the `urllib.request` module when the call is made, its reply
used only as a context manager and through `.read()`; an error status
arrives as `urllib.error.HTTPError`.

The request bodies, reply shapes and stop mapping for each provider are
`specs/architecture/tool-use-wire-formats.md`'s.

`serve_mcp` is the stdio MCP server the `claude-cli` loop starts as
`<sys.executable> <this module's file> --mcp-serve <socket_path> <tools_path>`;
running the module with those arguments calls it and exits with its
return value.

`claude_command` is run as argv[0] exactly as given, never shell-split.

Implements: `specs/architecture/tool-use-wire-formats.md`
