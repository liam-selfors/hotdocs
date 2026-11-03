# `SealedKey`

```json
{
  "owners": ["pipeline-team"],
  "source_path": "pipeline/criterion-compiler/",
  "source_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "verifier_version": "verifier-orchestrator@2.0.0"
}
```

Returned as an object exposing the four fields as attributes
(`R-PROVCHECK-007`). `owners` and `source_path` are copied from the
component's `component.md` frontmatter; `source_hash` and
`verifier_version` are computed or read as that requirement states.
