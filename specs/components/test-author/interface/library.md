# Library

```
author_test(
    bundle: CriterionBundle, model: str, seed: int = 0,
    *, repo_root: Path = None, llm_backend=None,
) -> TestAuthoringResult
```

Not a pure function: like `generator`'s `generate()`, it makes an
external call. `llm_backend` is passed straight to `llm-endpoint`'s
`backend` parameter, the seam every `AC-AUTHOR-*` mock uses (`D57`).
