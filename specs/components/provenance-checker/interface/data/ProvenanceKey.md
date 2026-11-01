# `ProvenanceKey`

```json
{
  "spec_bundle_hash": "sha256:...",
  "gate_versions": {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@3.1.0",
    "secret_scanner": "secret_scanner@0.0.0"
  }
}
```

`gate_versions` has exactly these five keys, each value copied
unchanged from the gate it names (`R-PROVCHECK-005`). Returned as an
object exposing both fields as attributes.
