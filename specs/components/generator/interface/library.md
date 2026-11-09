# Library

```
generate(
    bundle: SpecBundle, model: str, retry_feedback: list[str] | None = None,
    *, repo_root: Path = None, llm_backend=None,
) -> GenerationResult
```

Not a pure function — this is the one component in the corpus whose job
requires an external call. Side effects: in `cold` mode, writes
`gen/<component>/` and writes through `cache-manager`; in `hint` mode,
reads through `cache-manager` but writes to neither destination
(`R-GEN-016`).

`repo_root` locates `component.md`'s `sealed`/`source_path` and
`gen/<component>/.overrides.json` for `R-GEN-009`, and is where
`gen/<component>/` is written. `llm_backend` goes straight to
`llm-endpoint`'s `backend` parameter: the criteria's injected mock model.

```
GATE_VERSION = "generator@2.0.0"
PROMPT_VERSION = "v10"
```

The cache key (`R-GEN-005`) is `cache-manager`'s `CacheKey` with
`spec_bundle_hash` the bundle's, `gate_version` `GATE_VERSION`,
`model_pin` the `model` argument, and `gate_inputs_hash` `"sha256:"`
plus the SHA-256 hex digest of
`json.dumps(sorted(retry_feedback or []), sort_keys=True)` encoded as
UTF-8. Every result's `prompt_version` is `PROMPT_VERSION`.
