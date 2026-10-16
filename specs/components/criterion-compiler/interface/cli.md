# CLI

```
hotdocs compile-criteria <component-id> [--target=pytest] [--out=<dir>] [--repo-root=<dir>]
```

- `<component-id>` — the component whose `acceptance/` directory to
  compile. (Previously took `<acceptance.md>` + `--interface=<interface.md>`
  as explicit file paths; D15's one-file-per-unit layout made that
  unnecessary — given a component id and `--repo-root`, both
  `acceptance/*.md` and `interface/` are at known, derivable paths.)
- `--target` — emitted test-framework target. Default and only supported
  value for v1: `pytest` (Python). Multi-target emission is an open question
  (`component.md`).
- `--out` — output directory for compiled test files. Default:
  `verification/<component>/compiled/`.
- `--repo-root` — repository root. Defaults to the current git repository
  root, same as every other CLI in this corpus.

Step templates are not redefined here — see
`specs/architecture/step-phrase-grammar.md`, the corpus-wide convention
this component implements.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Every `kind: compiled` criterion compiled successfully. |
| `1` | ≥1 criterion failed to compile (unrecognized step, unresolved reference, literal-safety violation). |
| `2` | Usage error. |
