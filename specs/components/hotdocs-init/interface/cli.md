# CLI

```
hotdocs init [<dir>] [--example] [--reconfigure] [--provider <name>]
    [--model <name>] [--base-url <url>] [--api-key-env <NAME>]
    [--auth <login|key>] [--no-test] [--yes]
```

`main(argv)` receives everything after the `init` word. Every flag takes its
value as `--flag=value` or as the next argument; `--example`,
`--reconfigure`, `--no-test`, and `--yes` take none. `<dir>` defaults to the
current directory. Behavior is in `R-INIT-001`–`006`; usage errors in
`R-INIT-007`.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Finished, with every prerequisite present. |
| `1` | Refused before writing anything (a name collision, or `<dir>` is the tool's own repository), or `--reconfigure` on a directory that is not an initialised project, or on a failed save. |
| `2` | Usage error. |
| `3` | Finished, but a prerequisite is missing. |
