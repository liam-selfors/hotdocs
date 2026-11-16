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
and returns its result text and whether it is an error. `model` is a
model string (`llm-endpoint`'s `R-ENDPOINT-002`), resolved with
`llm-endpoint`'s `resolve_provider(model, load_config())`; the API key is
read from the environment variable the resolved `api_key_env` names.
`llm-endpoint` is loaded from `<repo_root>/gen/llm-endpoint/llm_endpoint.py`,
else from the tool root's copy. `ModelResolutionError` from it
propagates.

Every HTTP request is `urllib.request.urlopen(request, timeout=<seconds>)`,
looked up on the `urllib.request` module when the call is made, its reply
used only as a context manager and through `.read()`; an error status
arrives as `urllib.error.HTTPError`. A test replaces
`urllib.request.urlopen` with a function that records each
`Request`'s URL, headers and decoded JSON body and returns scripted
replies.

The request bodies, reply shapes and stop mapping for each provider are
`specs/architecture/tool-use-wire-formats.md`'s.

`serve_mcp` is the stdio MCP server the `claude-cli` loop starts as
`<sys.executable> <this module's file> --mcp-serve <socket_path> <tools_path>`;
running the module with those arguments calls it and exits with its
return value.

## Test fixtures

A **fake `claude`** is an executable Python script whose path is passed
as `claude_command`. It reads its own argv, takes the server command from
the JSON file after `--mcp-config` (`mcpServers.hotdocs.command` and
`.args`), starts it with stdin and stdout pipes, sends `initialize`, the
`notifications/initialized` notification, `tools/list` and any scripted
`tools/call` requests as JSON-RPC lines, then prints stream-json lines
ending with `{"type": "result", "subtype": "success", "is_error": false,
"result": "<text>", "num_turns": <n>}` and exits `0`.

Implements: `specs/architecture/tool-use-wire-formats.md`
