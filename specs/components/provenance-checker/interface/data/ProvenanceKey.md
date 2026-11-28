# `ProvenanceKey`

```json
{
  "spec_bundle_hash": "sha256:...",
  "spec_bundle_parts": {"spec": "sha256:...", "dependency_code": "sha256:..."},
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
              "versions": {"python": "3.14.6", "packages": "sha256:..."}, "lockfile_sha256": null},
             {"kind": "javascript", "path": "static/app.js",
              "definition_sha256": "sha256:...", "adapter_sha256": "sha256:...",
              "versions": {"node": "24.1.0"}, "lockfile_sha256": null}],
  "drivers": []
}
```

`gate_versions` has exactly these six keys, each value copied
unchanged from the gate it names; `generator` is its `GATE_VERSION`, a
`+`, and its `PROMPT_VERSION` (`R-PROVCHECK-005`). `assets` and `drivers` are the
component's current values (`R-PROVCHECK-009`), the `python` asset
entry first, alone when it declares none; callers never pass them to
`check_provenance`, which computes them itself. `spec_bundle_parts` is the bundle's own (`R-PROVCHECK-011`). Returned as an object exposing the five fields as
attributes; `spec_bundle_parts` is a plain `dict`, `gate_versions` is a plain `dict[str, str]`, `assets` and `drivers`
plain `list`s of `dict`.
