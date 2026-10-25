# Library

```
generate(bundle: SpecBundle, model: str, retry_feedback: list[str] | None = None) -> GenerationResult
```

Not a pure function — this is the one component in the corpus whose job
requires an external call. Side effects: writes `gen/<component>/`, reads
and writes through `cache-manager`.
