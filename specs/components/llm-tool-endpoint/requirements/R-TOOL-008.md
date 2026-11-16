# R-TOOL-008

**R-TOOL-008** — `serve_mcp(socket_path, tools_path)` MUST read one
  JSON-RPC 2.0 message per stdin line and write each reply as one line
  to stdout, flushed. `initialize` is answered with `{"protocolVersion":
  <the request's protocolVersion>, "capabilities": {"tools": {}},
  "serverInfo": {"name": "hotdocs", "version": "1"}}`; `tools/list` with
  `{"tools": [...]}`, each tool's `input_schema` given as `inputSchema`;
  `tools/call` by sending `{"name", "arguments"}` as one line over a
  connection to `socket_path`, reading one reply line, and answering
  `{"content": [{"type": "text", "text": <text>}], "isError": <is_error>}`.
  A notification (no `id`) gets no reply; any other method gets error
  code `-32601`. It returns `0` at the end of stdin.
