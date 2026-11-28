# Testing llm-tool-endpoint

All are `kind: generated-test`: the HTTP loops run against a replaced
`urllib.request.urlopen`, the `claude-cli` loop against a fake `claude`
script.

A test replaces
`urllib.request.urlopen` with a function that records each
`Request`'s URL, headers and decoded JSON body and returns scripted
replies: objects usable as a context manager whose `.read()` returns the
reply document as UTF-8 JSON bytes.

A loop test leaves `repo_root` `None`, unsets `VAR_HOTDOCS_CONFIG` and
runs from a fresh empty directory, so `load_config()` returns `None` and
a `<provider>:<model>` string takes `PROVIDERS`' defaults; a `claude-cli:`
model reads no key.

A **fake `claude`** is an executable Python script whose path is passed
as `claude_command`, run as argv[0] exactly as given, never shell-split: a
file starting `#!<sys.executable>` with its executable bit set. It reads its own argv, takes the server command from
the JSON file after `--mcp-config` (`mcpServers.hotdocs.command` and
`.args`), starts it with stdin and stdout pipes, sends `initialize`, the
`notifications/initialized` notification, `tools/list` and any scripted
`tools/call` requests as JSON-RPC lines, then prints stream-json lines
ending with `{"type": "result", "subtype": "success", "is_error": false,
"result": "<text>", "num_turns": <n>}` and exits `0`.
