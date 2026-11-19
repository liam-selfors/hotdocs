# CLI

```
hotdocs verify-component <component-id> [--repo-root=<dir>] [--format=json|text]
```

`main(argv)` receives `argv` beginning with `<component-id>`. Each flag
takes its value as `--flag=value` or as the next argument;
`--repo-root` defaults to the current directory, `--format` to `text`.
`json` prints the `VerificationReport`; `text` prints `<component_id>:
<overall>` then one indented `<criterion id>: <result>` line each.

| Exit | Meaning |
| --- | --- |
| `0` | Overall verdict `pass`. |
| `1` | Overall verdict `fail`. |
| `2` | Usage error: no `<component-id>`, invalid `--format`, unknown argument, a flag last with no value, or no `specs/components/<slug>/component.md`. |
