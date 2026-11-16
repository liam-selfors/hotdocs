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
A mock replies `-----BEGIN FILE <n>-----`, the file, then
`-----END FILE <n>-----`, `<n>` the `secrets.token_hex(16)` nonce read
from the prompt.

Each dependency (`cache-manager`, `llm-endpoint`, `test-probe`) is
loaded from `<repo_root>/gen/<slug>/<module>.py`, else from the tool
root's copy. A test replaces `test-probe` with a stand-in at
`<repo_root>/gen/test-probe/test_probe.py` defining
`probe(test_source, criterion_bundle, module_name, *, timeout=60.0)` that
returns an object with `ok` (bool), `findings` (a list of dicts with
`kind`, `severity`, `line`, `message`) and `to_dict()`.
