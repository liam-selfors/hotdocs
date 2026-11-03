# CLI

```
hotdocs <verb words> [args...]
hotdocs [--help | -h | help | --version]
```

`main(argv)` receives everything after the `hotdocs` word. Verbs route per
`interface/data/VerbTable.md` (`R-CLI-001`–`005`), `init` included; help and
version are `R-CLI-004`.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Help or version; or a routed verb whose component returned `0`. |
| `2` | Unknown verb; a verb whose component file or `main` is missing. |
| other | A routed verb returns its component's own code. |
