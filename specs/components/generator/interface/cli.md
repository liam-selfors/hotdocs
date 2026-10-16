# CLI

```
hotdocs generate <component-id> --model=<model-id> [--seed=<n>] [--repo-root=<dir>] [--format=json|text]
```

- `<component-id>` — target component.
- `--model` — model identifier to call (R-GEN-004). Required — there is no
  implicit default, even for "the canonical pin," to keep this component
  honest about never hardcoding which model it calls.
- `--seed` — sample seed/index (R-GEN-007). Default `0`.
- Bundle mode (`cold`/`hint`) is inherited from whatever `SpecBundle` is
  passed in — this component does not itself choose a mode, it consumes
  whatever `spec-bundle-assembler` produced.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | A candidate was produced (from cache or a fresh model call) and written. |
| `1` | Model-call error (R-GEN-008) — distinct from "produced code that later fails verification," which still exits `0` here. |
| `2` | Usage error (unknown component id, missing `--model`). |
