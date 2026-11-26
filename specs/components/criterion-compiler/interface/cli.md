# CLI

```
hotdocs compile-criteria <component-id> [--target=pytest] [--out=<dir>] [--repo-root=<dir>]
```

`main(argv: list[str] | None = None) -> int` gets the tokens after
`compile-criteria` (`hotdocs-cli` strips the verb) and returns the exit
code.

- `<component-id>` — the component whose `acceptance/` directory to
  compile.
- `--target` — emitted test-framework target. Default and only supported
  value for v1: `pytest` (Python); any value other than `pytest` is a
  usage error (exit `2`), never a silent fallback (R-COMPILE-011).
- `--out` — output directory for compiled test files. Default:
  `verification/<component>/compiled/`.
- `--repo-root` — repository root. Defaults to the current git repository
  root.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Every `kind: compiled` criterion compiled successfully. |
| `1` | ≥1 criterion failed to compile (unrecognized step, unresolved reference, literal-safety violation). |
| `2` | Usage error — unknown component id, missing required argument, or an unsupported `--target` value (R-COMPILE-011). |
