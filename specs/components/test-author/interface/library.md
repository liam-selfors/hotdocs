# Library

```
author_test(
    bundle: CriterionBundle, model: str, seed: int = 0,
    *, repo_root: Path = None, llm_backend=None,
) -> TestAuthoringResult
GATE_VERSION = "generated_test@2.2.0"
```

Not a pure function: like `generator`'s `generate()`, it makes an
external call. `llm_backend` is passed straight to `llm-endpoint`'s
`backend` parameter, the seam every `AC-AUTHOR-*` mock uses (`D57`).
Each dependency (`cache-manager`, `llm-endpoint`, `test-probe`) is
loaded from `<repo_root>/gen/<slug>/<module>.py`, else from the tool
root's copy. The reply format, the `test-probe` stand-in and the
written file are in `specs/architecture/test-author-fixtures.md`; the
exact returned, written and cached content, and how a test compares
it, in `specs/architecture/test-author-output.md`; the prompt's fixed
rule blocks in `specs/architecture/test-author-prompt.md`.

Implements: `specs/architecture/cli-conventions.md`, `specs/architecture/test-author-fixtures.md`, `specs/architecture/test-author-output.md`, `specs/architecture/test-author-prompt.md`
