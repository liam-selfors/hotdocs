# AC-TOOL-008

Covers: R-TOOL-008
Kind: generated-test

```gherkin
Given a tools file holding one tool {"name": "t", "description": "d",
  "input_schema": {"type": "object"}}, a Unix socket the test listens on
  that answers each request line with {"text": "r", "is_error": false},
  and serve_mcp started in a subprocess as
  "<python> <module file> --mcp-serve <socket> <tools file>"
When the test writes the lines: initialize with id 1 and protocolVersion
  "2025-06-18", a notifications/initialized notification, tools/list with
  id 2, tools/call with id 3 for "t" with arguments {"a": 1}, and
  bogus/method with id 4, then closes stdin
Then stdout holds exactly four reply lines: id 1's result has
  protocolVersion "2025-06-18" and capabilities {"tools": {}}; id 2's
  tools[0] has inputSchema {"type": "object"}; id 3's result is
  {"content": [{"type": "text", "text": "r"}], "isError": false} and the
  socket received {"name": "t", "arguments": {"a": 1}}; id 4 has error
  code -32601; and the process exits 0
```
