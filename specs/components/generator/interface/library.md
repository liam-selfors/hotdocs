# Library

```
generate(
    bundle: SpecBundle, model: str, retry_feedback: list[str] | None = None,
    *, repo_root: Path = None, llm_backend=None,
) -> GenerationResult
commit_cache(result: GenerationResult, repo_root: Path = None) -> None
check_write_allowed(bundle: SpecBundle, repo_root: Path = None) -> str | None
render_prompt_sections(bundle: SpecBundle, retry_feedback: list[str] | None = None) -> list[tuple[str, str]]
write_files(component_id: str, files: dict[str, str], repo_root: Path = None) -> None
```

Not a pure function — this is the one component in the corpus whose job
requires an external call. Side effects: in `cold` mode, `generate`
writes `gen/<component>/`; in `hint` mode it writes nothing
(`R-GEN-016`). Only `commit_cache` writes the cache (`R-GEN-006`).

`repo_root` locates `component.md`'s `sealed`/`source_path` and
`gen/<component>/.overrides.json` for `R-GEN-009`, and is where
`gen/<component>/` is written. `llm_backend` goes straight to
`llm-endpoint`'s `backend` parameter: the criteria's injected mock model.

The helpers are the pieces `generate` itself uses, for another
generation mode to share:

- `check_write_allowed` returns `R-GEN-009`'s refusal reason
  (`"sealed-component"`, `"pinned-override"`) or `None`;
- `render_prompt_sections` returns the prompt's bundle-derived sections
  as `(title, text)` pairs in prompt order, `retry_feedback`'s last when
  given, without the reply-format instructions;
- `write_files` writes `files` (paths relative to `gen/<component>/`,
  `R-GEN-015`'s prefix stripped) into `gen/<component>/`.

## Reply format

The model's reply, a mock's included, wraps each file as a line
`-----BEGIN FILE <nonce>: <path>-----`, the file's content, then a line
`-----END FILE <nonce>-----`, and ends with the line
`-----END REPLY <nonce>-----` (`R-GEN-021`): `<path>` relative to
`gen/<component>/`, `<nonce>` the fresh `uuid.uuid4().hex` the prompt
states for this call. Text outside the blocks is ignored.

```
GATE_VERSION = "generator@3.0.0"
PROMPT_VERSION = "v11"
```

The cache key (`R-GEN-005`) is `cache-manager`'s `CacheKey` with
`spec_bundle_hash` the bundle's, `gate_version` `GATE_VERSION`,
`model_pin` the `model` argument, and `gate_inputs_hash` `"sha256:"`
plus the SHA-256 hex digest of
`json.dumps(sorted(retry_feedback or []), sort_keys=True)` encoded as
UTF-8. Every result's `prompt_version` is `PROMPT_VERSION`.
