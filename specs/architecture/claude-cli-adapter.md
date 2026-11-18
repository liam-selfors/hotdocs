---
id: arch-claude-cli-adapter
title: The claude-cli Adapter
status: draft
owners: [pipeline-team]
depends_on: []
---

# The claude-cli Adapter

## Purpose

How `llm-endpoint`'s `claude-cli` provider runs the `claude` command:
its arguments, its environment, how its output becomes a reply, and how
a failure is classified.

## Rules

### The command

Every call runs the command named `claude`, found on `PATH` when the
call is made, through `subprocess.run`, with the prompt on standard
input and the provider's timeout (`R-ENDPOINT-004`):

```
claude -p --model <model> --tools "" --output-format stream-json --verbose <auth flag> [--<param> <value>]...
```

`--tools ""` (`D35`) keeps the command from using any tool. Each entry
of `**params` becomes `--<name with _ as ->` and its value as a string.

### Authentication

The `[llm]` table's `auth` entry (`R-ENDPOINT-007`) decides the auth
flag and the command's environment (`D82`, `D322`):

| `auth` | auth flag | environment |
| --- | --- | --- |
| `"login"` | `--safe-mode` | this process's environment without `ANTHROPIC_API_KEY` |
| `"key"` | `--bare` | this process's environment |
| unset | `--bare` when `ANTHROPIC_API_KEY` is set and non-empty, else `--safe-mode` | this process's environment |

`--bare` makes the command authenticate with `ANTHROPIC_API_KEY` and
refuses a claude.ai login; `--safe-mode` uses the login. A process
started by Claude Code inherits an `ANTHROPIC_API_KEY` that is not valid
for a separate `claude -p` call, so a person whose `claude` is logged in
sets `auth = "login"`. The adapter never checks for a credential before
running the command.

### The reply

The reply is every `text` block of every `assistant` event's
`message.content`, in order, joined with nothing between them (`D225`).
Each non-blank line of standard output is one JSON event. A `result`
event whose `is_error` is true, or a non-zero exit, is a failure. When
standard output is not that stream (a line that is not a JSON object,
or no line at all), a zero exit makes the whole of standard output the
reply, unchanged, and a non-zero exit is a failure.

### Failures

A failure is classified from a text, lowercased: when standard output
is the stream, the failing `result` events' `result` text and standard
error together; otherwise standard output and standard error together.
The category is the first of these lists holding one of its markers in
that text: `rate_limit` (`rate limit`,
`rate_limit`, `429`), `auth` (`auth`, `login`, `api key`, `401`, `403`),
`timeout` (`timed out`, `timeout`); otherwise `network`. A run past the
timeout is `timeout`. The message is `claude command failed (<category>)`.

When the category is `auth`, `auth` is unset and the auth flag was
`--bare`, the message is instead:

```
claude command failed (auth): ANTHROPIC_API_KEY is set, so claude used it instead of your claude.ai login; unset it, or set auth = "login" in hotdocs.toml's [llm] table
```

### Test fixtures

A test replaces the command by writing an executable file named
`claude` into a temporary directory placed first on `PATH`
(`monkeypatch.setenv("PATH", ...)`). The script records its arguments
and, to observe the environment, `os.environ.get("ANTHROPIC_API_KEY")`,
by appending to a file the test controls, then prints stream events.
