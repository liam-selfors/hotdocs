---
id: comp-test-author-interface
title: Test Author — Interface
status: draft
owners: [pipeline-team]
---

# Test Author — Interface

## CLI

```
hotdocs author-test <component-id> <criterion-id> --model=<model-id> [--seed=<n>] [--repo-root=<dir>] [--format=json|text]
```

- `<criterion-id>` — the acceptance criterion's own id (e.g. `AC-FOO-003`).
- `--model` — required, same discipline as `generator`'s `--model`: never
  an implicit default.

**Exit codes:**

| Code | Meaning |
| --- | --- |
| `0` | Test code produced (from cache or a fresh model call) and written. |
| `1` | Model-call error (R-AUTHOR-007). |
| `2` | Usage error. |

## Library

```
author_test(bundle: CriterionBundle, model: str, seed: int = 0) -> TestAuthoringResult
```

Not a pure function, same as `generator`'s `generate()` — this is the
second component in the corpus whose job requires an external call.

## Data: `CriterionBundle`

```json
{
  "component_id": "comp-foo",
  "criterion_id": "AC-FOO-003",
  "covers": "R-FOO-003",
  "criterion_text": "<Given/When/Then prose>",
  "requirement_text": "<the covered R-id's own text from spec.md>",
  "interface": "<interface.md body>",
  "glossary": "<specs/glossary.md body>"
}
```

Assembled by `spec-bundle-assembler` (a new library entry point alongside
`assemble()`, narrower in scope and never including `gen/<component>/`
content, per R-AUTHOR-002).

## Data: `TestAuthoringResult`

```json
{
  "component_id": "comp-foo",
  "criterion_id": "AC-FOO-003",
  "model": "claude-sonnet-5",
  "seed": 0,
  "prompt_version": "v1",
  "cache_hit": false,
  "file": { "path": "verification/foo/generated-test/test_ac_foo_003.py", "content": "<test code>" },
  "model_call_error": null
}
```
