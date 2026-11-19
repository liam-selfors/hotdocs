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
  },
  "assets": [{"kind": "python", "path": ".",
              "definition_sha256": "sha256:...", "adapter_sha256": "sha256:...",
              "versions": {"python": "3.12"}, "lockfile_sha256": null},
             {"kind": "javascript", "path": "static/app.js",
              "definition_sha256": "sha256:...", "adapter_sha256": "sha256:...",
              "versions": {"node": "24.1.0"}, "lockfile_sha256": null}]
}
```

`gate_versions` has exactly these six keys, each value copied
unchanged from the gate it names; `generator` is its `GATE_VERSION`, a
`+`, and its `PROMPT_VERSION` (`R-PROVCHECK-005`). `assets` is the
component's current assets value (`R-PROVCHECK-009`), the `python`
entry first, alone when it declares none; callers never pass it to `check_provenance`, which
computes it itself. Returned as an object exposing the three fields as
attributes; `gate_versions` is a plain `dict[str, str]`, `assets` a
plain `list` of `dict`.
