---
id: arch-tool-use-wire-formats
title: Tool-Use Wire Formats
status: draft
owners: [pipeline-team]
depends_on: []
---

# Tool-Use Wire Formats

## Purpose

The exact request and reply shapes a multi-turn tool loop exchanges with
each provider that supports tools, so an implementation and its tests
build the same JSON. A tool is given to every provider as
`{"name": <str>, "description": <str>, "input_schema": <JSON Schema object>}`
and translated as below.

## `anthropic`

`POST {base}/v1/messages`, headers `x-api-key: <key>`,
`anthropic-version: 2023-06-01`, `content-type: application/json`.

Request body:

```json
{"model": "<m>", "max_tokens": 32000,
 "system": [{"type": "text", "text": "<system>", "cache_control": {"type": "ephemeral"}}],
 "tools": [{"name": "...", "description": "...", "input_schema": {...}}],
 "tool_choice": {"type": "auto"},
 "messages": [{"role": "user", "content": "<prompt>"}]}
```

No `temperature`, `top_p`, `top_k`, `thinking` or `budget_tokens` is
sent: current models reject them. `tool_choice` is always `auto`; current
models reject `any` and `tool`.

Reply: `content` is a list of blocks; `text` blocks carry `text`,
`tool_use` blocks carry `id`, `name` and `input` (an object), and
`thinking` blocks are kept in the transcript but contribute no text.
`stop_reason` decides the next step:

| `stop_reason` | Loop action |
| --- | --- |
| `tool_use` | run every `tool_use` block, then send one user message with all results |
| `end_turn`, `stop_sequence` | stop: `end_turn` |
| `pause_turn` | send the reply back unchanged as the assistant turn and continue |
| `max_tokens` | stop: `truncated` |
| `refusal` | stop: `refusal` |

The assistant turn appended to `messages` is the reply's whole `content`
list, unchanged. Results go back as one user message:

```json
{"role": "user", "content": [
  {"type": "tool_result", "tool_use_id": "<id>", "content": "<text>"},
  {"type": "tool_result", "tool_use_id": "<id2>", "content": "<error text>", "is_error": true}]}
```

## `openai` and `openai-compatible`

`POST {base}/chat/completions`, `Authorization: Bearer <key>` (for
`openai-compatible` only when a key is configured).

Request body: `{"model", "messages", "tools", "tool_choice": "auto"}`,
plus `max_completion_tokens` for `openai` or `max_tokens` for
`openai-compatible`. The system text is the first message,
`{"role": "system", "content": "<system>"}`. Each tool is
`{"type": "function", "function": {"name", "description", "parameters": <input_schema>}}`.

Reply: `choices[0].message` and `choices[0].finish_reason`. The message's
`tool_calls` is a list of
`{"id", "type": "function", "function": {"name", "arguments": "<JSON text>"}}`;
`arguments` is parsed with `json.loads`, and text that does not parse to an
object is returned to the model as an error result.

| `finish_reason` | Loop action |
| --- | --- |
| `tool_calls` | run every call, then send one `tool` message per call |
| `stop` | stop: `end_turn` |
| `length` | stop: `truncated` |
| `content_filter` | stop: `refusal` |

The assistant message is appended unchanged; each result follows it as
`{"role": "tool", "tool_call_id": "<id>", "content": "<text>"}`.

## `claude-cli`

The tools are served by a stdio MCP server (JSON-RPC 2.0, one message per
line) answering `initialize`, `tools/list` and `tools/call`; a
`tools/call` result is `{"content": [{"type": "text", "text": "<text>"}],
"isError": <bool>}`. The command is:

```
claude -p --model <m> --output-format stream-json --verbose
  --tools "" --mcp-config <cfg.json> --strict-mcp-config
  --allowedTools mcp__hotdocs__<tool> ... --no-session-persistence
  --setting-sources "" --disable-slash-commands
  --settings '{"autoMemoryEnabled":false,"disableAllHooks":true}'
  --system-prompt <system>
```

with the prompt on stdin. `--safe-mode` is never passed here: it disables
every MCP server. The flags above keep the user's CLAUDE.md, AGENTS.md,
skills, hooks and memory out of the call and expose only the listed
tools. Stdout is newline-delimited JSON events; the final
`{"type": "result"}` event gives `result` (the text), `is_error` and
`num_turns`. The loop's turn and tool-call caps are enforced by the MCP
server, which answers every call past a cap with an error result, and the
wall-clock cap by killing the process.

## `gemini`, `ollama`

Tool use is not supported; a tool loop over either raises before any
request is sent.
