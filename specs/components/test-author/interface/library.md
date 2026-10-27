# Library

```
author_test(
    bundle: CriterionBundle, model: str, seed: int = 0,
    *, repo_root: Path = None, llm_backend=None,
) -> TestAuthoringResult
```

Not a pure function, same as `generator`'s `generate()` — this is the
second component in the corpus whose job requires an external call.

`repo_root` and `llm_backend` (`D57`, a real, pre-existing gap: every
`AC-AUTHOR-*` criterion already required "an injected mock model," but
this signature never actually declared the parameter that injects
one) — `llm_backend`, passed straight through to `llm-endpoint`'s own
`backend` parameter, is how every one of those criteria's mock model
is actually wired in, mirroring `generator`'s own `llm_backend`
exactly, same name, same seam, not a second one.
