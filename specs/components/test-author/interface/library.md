# Library

```
author_test(
    bundle: CriterionBundle, model: str, seed: int = 0,
    *, repo_root: Path = None, llm_backend=None,
) -> TestAuthoringResult
GATE_VERSION = "generated_test@1.1.0"
```

Not a pure function: like `generator`'s `generate()`, it makes an
external call. `llm_backend` is passed straight to `llm-endpoint`'s
`backend` parameter, the seam every `AC-AUTHOR-*` mock uses (`D57`).
A mock replies `-----BEGIN FILE <n>-----`, the file, then
`-----END FILE <n>-----`, `<n>` the `secrets.token_hex(16)` nonce read
from the prompt. The prompt's fixed rule blocks are in
`specs/architecture/test-author-prompt.md`.

Implements: `specs/architecture/test-author-output.md`, `specs/architecture/test-author-prompt.md`
