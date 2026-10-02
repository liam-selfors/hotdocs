---
id: comp-generator-interface
title: Generator — Interface
status: draft
owners: [pipeline-team]
---

# Generator — Interface

## CLI

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

## Library

```
generate(bundle: SpecBundle, model: str, seed: int = 0) -> GenerationResult
```

Not a pure function — this is the one component in the corpus whose job
requires an external call. Side effects: writes `gen/<component>/`, reads
and writes through `cache-manager`.

## Data: `GenerationResult`

```json
{
  "component_id": "comp-foo",
  "model": "claude-sonnet-5",
  "seed": 0,
  "prompt_version": "v1",
  "cache_hit": false,
  "files": { "spec_linter.py": "<file content>" },
  "model_call_error": null
}
```

`model_call_error` is `null` on success; when non-null (R-GEN-008), `files`
MUST be empty and `cache_hit` MUST be `false` — a failed call never produces
partial output.
