# `ProvenanceKey`

```json
{
  "spec_bundle_hash": "sha256:...",
  "gate_versions": {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11"
  }
}
```

`gate_versions` has exactly these six keys, each value copied
unchanged from the gate it names; `generator` is its `GATE_VERSION`, a
`+`, and its `PROMPT_VERSION` (`R-PROVCHECK-005`). Returned as an
object exposing both fields as attributes; `gate_versions` is a plain
`dict[str, str]`.
