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

`compile` returns a `CompileReport` dataclass with attributes `outputs`
(dicts as above), `gate_version` and `summary` (a dict). An error's
`message` quotes the offending step text or name, and contains `does not
match any recognized template` for an unmatched step, `unresolved
reference '<name>'` for an identifier no earlier `Given` binds, `does not
resolve` for a name the interface lacks, and `is not a literal`
for an expression, plus `field/index access` when it is one.

`gate_version` corresponds to the `gate_versions.compiler` entry in the
provenance manifest described in `notes/initial-ideas.md`'s own D7
(R-COMPILE-010).
