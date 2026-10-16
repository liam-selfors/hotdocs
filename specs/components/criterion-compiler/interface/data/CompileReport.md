# `CompileReport`

```json
{
  "outputs": [
    {
      "criterion_id": "AC-LINT-003",
      "covers": "R-LINT-003",
      "status": "compiled",
      "file": "verification/spec-linter/compiled/test_ac_lint_003.py"
    },
    {
      "criterion_id": "AC-LINT-999",
      "covers": "R-LINT-999",
      "status": "error",
      "message": "step 'When a wizard appears' does not match any recognized template"
    }
  ],
  "gate_version": "criterion-compiler@1.0.0",
  "summary": {
    "compiled": 14,
    "errors": 0,
    "skipped_non_compiled_kind": 0
  }
}
```

`gate_version` corresponds to the `gate_versions.compiler` entry in the D7
provenance manifest (R-COMPILE-010).
