# CLI

```
hotdocs <verb words> [args...]
hotdocs <verb words> --help
hotdocs [--help | -h | help | --version]
```

`main(argv)` and `run(argv, ...)` receive everything after the `hotdocs` word. Verbs route per
`interface/data/VerbTable.md` (`R-CLI-001`–`005`), `init` included; help and
version are `R-CLI-004`. `--help` or `-h` after a verb's words prints
`hotdocs <verb words>: <summary>` and the component's usage line
(`R-CLI-007`).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Help or version; a verb's help (`R-CLI-007`); or a routed verb whose component returned `0`. |
| `2` | Unknown verb; a verb whose component file or `main` is missing; or a routed verb whose `main` raised an exception whose class is named `ModelResolutionError`. |
| other | A routed verb returns its component's own code. |

`llm-endpoint`'s `ModelResolutionError` means the `--model` given names
no provider. Components load their own copies of `llm-endpoint`, so it is
matched by class name, never by identity: `run` prints
`usage error: <its message>` to stderr, one line, never a traceback, and
returns `2`. Any other exception propagates.
